"""
数据采集Agent
封装所有市场数据和新闻数据的并行采集逻辑
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

from src.data_collectors.binance_futures import BinanceFuturesCollector
from src.data_collectors.news_collector import NewsCollector

logger = logging.getLogger(__name__)


class DataAgent:
    """
    数据采集Agent

    负责：
    - 并行采集多周期K线数据
    - 采集市场综合指标（资金费率、持仓量、多空比）
    - 采集新闻和恐慌贪婪指数
    - 错误处理和重试
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # 秒

    def __init__(
        self,
        binance: Optional[BinanceFuturesCollector] = None,
        news: Optional[NewsCollector] = None,
        binance_api_key: str = "",
        binance_api_secret: str = "",
        brave_api_key: str = "",
        proxy: str = "",
    ):
        self.binance = binance or BinanceFuturesCollector(
            api_key=binance_api_key,
            api_secret=binance_api_secret,
            proxy=proxy,
        )
        self.news = news or NewsCollector(
            brave_api_key=brave_api_key,
            proxy=proxy,
        )
        self._proxy = proxy

    async def _retry(self, coro, name: str):
        """带重试的异步调用"""
        for attempt in range(self.MAX_RETRIES):
            try:
                return await coro
            except Exception as e:
                logger.warning(f"{name} failed (attempt {attempt+1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"{name} failed after {self.MAX_RETRIES} attempts")
                    return None

    async def collect_all(
        self,
        symbol: str,
        timeframes: list[str],
        include_news: bool = True,
    ) -> dict:
        """
        并行采集所有数据

        Returns:
            {
                "klines": {"1H": [...], "4H": [...], ...},
                "market": {...},
                "news": [...],
                "fear_greed": {...},
                "timestamp": "...",
            }
        """
        logger.info(f"DataAgent: collecting all data for {symbol}")

        # 构建并行任务
        tasks = {}

        # 多周期K线采集
        for tf in timeframes:
            tasks[f"klines_{tf}"] = self._retry(
                self.binance.get_klines(symbol, tf, limit=200),
                f"klines_{symbol}_{tf}"
            )

        # 市场指标
        tasks["market"] = self._retry(
            self.binance.get_market_summary(symbol),
            f"market_{symbol}"
        )

        # 新闻数据
        if include_news:
            tasks["news"] = self._retry(
                self.news.get_symbol_news(symbol),
                f"news_{symbol}"
            )
            tasks["fear_greed"] = self._retry(
                self.news.get_fear_greed_index(),
                "fear_greed"
            )
            tasks["crypto_news_rss"] = self._retry(
                self.news.get_crypto_news_rss(count=5),
                "crypto_news_rss"
            )
            tasks["coingecko_global"] = self._retry(
                self.news.get_coingecko_global(),
                "coingecko_global"
            )

        # 并行执行
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # 整理结果
        output = {
            "klines": {},
            "market": {},
            "news": [],
            "fear_greed": {},
            "crypto_news_rss": [],
            "coingecko_global": {},
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        for (key, _), result in zip(tasks.items(), results):
            if isinstance(result, Exception):
                logger.error(f"Task {key} raised exception: {result}")
                continue

            if key.startswith("klines_"):
                tf = key[7:]  # 去掉 "klines_" 前缀
                if result:
                    output["klines"][tf] = result
            elif key == "market":
                if result:
                    output["market"] = result
            elif key == "news":
                if result:
                    output["news"] = result
            elif key == "fear_greed":
                if result:
                    output["fear_greed"] = result
            elif key == "crypto_news_rss":
                if result:
                    output["crypto_news_rss"] = result
            elif key == "coingecko_global":
                if result:
                    output["coingecko_global"] = result

        logger.info(
            f"DataAgent: collected {sum(len(v) for v in output['klines'].values())} klines, "
            f"{len(output['news'])} news items for {symbol}"
        )

        return output

    async def collect_klines(
        self,
        symbol: str,
        timeframes: list[str],
    ) -> dict[str, list]:
        """
        仅采集多周期K线

        Returns:
            {"1H": [...], "4H": [...], ...}
        """
        tasks = {
            tf: self._retry(
                self.binance.get_klines(symbol, tf, limit=200),
                f"klines_{symbol}_{tf}"
            )
            for tf in timeframes
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        klines = {}
        for (tf, _), result in zip(tasks.items(), results):
            if not isinstance(result, Exception) and result:
                klines[tf] = result

        return klines

    async def collect_market_metrics(self, symbol: str) -> dict:
        """
        采集市场综合指标

        Returns:
            包含价格、资金费率、持仓量、多空比的字典
        """
        result = await self._retry(
            self.binance.get_market_summary(symbol),
            f"market_{symbol}"
        )
        return result or {}

    async def collect_news(self, symbol: str) -> tuple[list, dict]:
        """
        采集新闻和恐慌贪婪指数

        Returns:
            (news_items, fear_greed_data)
        """
        news, fear_greed = await asyncio.gather(
            self._retry(
                self.news.get_symbol_news(symbol),
                f"news_{symbol}"
            ),
            self._retry(
                self.news.get_fear_greed_index(),
                "fear_greed"
            ),
        )
        return news or [], fear_greed or {}

    async def close(self):
        """关闭所有连接"""
        await self.binance.close()
        await self.news.close()
