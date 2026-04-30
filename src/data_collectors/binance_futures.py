"""
Binance Futures 数据采集模块
采集合约市场数据：K线、资金费率、持仓量、多空比等
"""
import aiohttp
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BinanceFuturesCollector:
    """Binance合约数据采集器"""

    BASE_URL = "https://fapi.binance.com"

    # K线周期映射
    INTERVAL_MAP = {
        "15m": "15m", "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1w"
    }

    def __init__(self, api_key: str = "", api_secret: str = "", proxy: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.proxy = proxy
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _request(self, endpoint: str, params: dict = None) -> dict | list:
        """发送API请求"""
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"
        headers = {}
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        connector = aiohttp.TCPConnector() if not self.proxy else aiohttp.TCPConnector(
            ssl=False
        )

        async with session.get(url, params=params, headers=headers, proxy=self.proxy or None) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"Binance API error ({resp.status}): {error_text}")
                raise Exception(f"Binance API error: {resp.status}")
            return await resp.json()

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 200,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> list[dict]:
        """
        获取K线数据

        Returns:
            [{"open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", ...}]
        """
        binance_interval = self.INTERVAL_MAP.get(interval, interval)
        params = {
            "symbol": symbol,
            "interval": binance_interval,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = await self._request("/fapi/v1/klines", params)

        klines = []
        for item in data:
            klines.append({
                "open_time": item[0],
                "open_time_str": datetime.fromtimestamp(item[0] / 1000).strftime("%Y-%m-%d %H:%M"),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "close_time": item[6],
                "quote_volume": float(item[7]),
                "trades": item[8],
                "taker_buy_volume": float(item[9]),
                "taker_buy_quote_volume": float(item[10]),
            })

        return klines

    async def get_ticker_price(self, symbol: str) -> dict:
        """获取最新价格"""
        data = await self._request("/fapi/v1/ticker/price", {"symbol": symbol})
        return {
            "symbol": data["symbol"],
            "price": float(data["price"]),
            "time": datetime.fromtimestamp(data["time"] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def get_24h_ticker(self, symbol: str) -> dict:
        """获取24h行情数据"""
        data = await self._request("/fapi/v1/ticker/24hr", {"symbol": symbol})
        return {
            "symbol": data["symbol"],
            "price": float(data["lastPrice"]),
            "price_change": float(data["priceChange"]),
            "price_change_pct": float(data["priceChangePercent"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "volume": float(data["volume"]),
            "quote_volume": float(data["quoteVolume"]),
            "trades": data["count"],
        }

    async def get_funding_rate(self, symbol: str, limit: int = 30) -> list[dict]:
        """获取资金费率历史"""
        data = await self._request("/fapi/v1/fundingRate", {
            "symbol": symbol,
            "limit": limit,
        })
        return [{
            "funding_rate": float(item["fundingRate"]),
            "funding_time": datetime.fromtimestamp(item["fundingTime"] / 1000).strftime("%Y-%m-%d %H:%M"),
        } for item in data]

    async def get_open_interest(self, symbol: str) -> dict:
        """获取持仓量"""
        data = await self._request("/fapi/v1/openInterest", {"symbol": symbol})
        return {
            "symbol": data["symbol"],
            "open_interest": float(data["openInterest"]),
            "time": datetime.fromtimestamp(data["time"] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def get_long_short_ratio(self, symbol: str, period: str = "5m", limit: int = 30) -> list[dict]:
        """获取大户多空比"""
        data = await self._request("/futures/data/topLongShortPositionRatio", {
            "symbol": symbol,
            "period": period,
            "limit": limit,
        })
        return [{
            "long_pct": float(item["longAccount"]),
            "short_pct": float(item["shortAccount"]),
            "long_short_ratio": float(item["longShortRatio"]),
            "time": datetime.fromtimestamp(item["timestamp"] / 1000).strftime("%Y-%m-%d %H:%M"),
        } for item in data]

    async def get_global_long_short_ratio(self, symbol: str, period: str = "5m", limit: int = 30) -> list[dict]:
        """获取全市场多空比"""
        data = await self._request("/futures/data/globalLongShortAccountRatio", {
            "symbol": symbol,
            "period": period,
            "limit": limit,
        })
        return [{
            "long_pct": float(item["longAccount"]),
            "short_pct": float(item["shortAccount"]),
            "long_short_ratio": float(item["longShortRatio"]),
            "time": datetime.fromtimestamp(item["timestamp"] / 1000).strftime("%Y-%m-%d %H:%M"),
        } for item in data]

    async def get_market_summary(self, symbol: str) -> dict:
        """获取市场综合数据"""
        ticker, funding, oi, ls_ratio = await asyncio.gather(
            self.get_24h_ticker(symbol),
            self.get_funding_rate(symbol, limit=1),
            self.get_open_interest(symbol),
            self.get_long_short_ratio(symbol, limit=1),
        )

        return {
            "symbol": symbol,
            "price": ticker["price"],
            "change_24h": ticker["price_change_pct"],
            "high_24h": ticker["high"],
            "low_24h": ticker["low"],
            "volume_24h": ticker["volume"],
            "funding_rate": funding[0]["funding_rate"] if funding else 0,
            "open_interest": oi["open_interest"],
            "long_short_ratio": ls_ratio[0]["long_short_ratio"] if ls_ratio else 1.0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# 需要导入
import asyncio
