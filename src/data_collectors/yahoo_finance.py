"""
Yahoo Finance 数据采集模块
采集非加密品种数据：黄金、白银、原油、股指等
使用 yfinance 库，通过 asyncio.to_thread 包装为异步接口
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

import yfinance as yf

logger = logging.getLogger(__name__)


class YahooFinanceCollector:
    """Yahoo Finance 数据采集器（黄金、白银、原油、指数等）"""

    # 品种代码映射
    SYMBOL_MAP = {
        "XAUUSD": "GC=F",   # 黄金期货
        "XAGUSD": "SI=F",   # 白银期货
        "USOIL":  "CL=F",   # 原油期货
        "SPX500": "^GSPC",  # 标普500
        "NAS100": "^IXIC",  # 纳斯达克100
        "DJI":    "^DJI",   # 道琼斯
        "US30":   "^DJI",
        "VIX":    "^VIX",   # 波动率指数
        "US10Y":  "^TNX",   # 10年期美债收益率
        "DXY":    "DX-Y.NYB",  # 美元指数
    }

    # K线周期映射（yfinance interval）
    INTERVAL_MAP = {
        "1h":  "1h",
        "1H":  "1h",
        "4H":  "1h",       # yfinance 不支持4h，用1h代替
        "1D":  "1d",
        "1W":  "1wk",
        "1M":  "1mo",
    }

    # K线周期对应的 yfinance period
    PERIOD_MAP = {
        "1h":  "60d",
        "1H":  "60d",
        "4H":  "60d",
        "1D":  "2y",
        "1W":  "5y",
        "1M":  "10y",
    }

    def __init__(self, proxy: str = ""):
        self.proxy = proxy

    def _resolve_symbol(self, symbol: str) -> str:
        """将内部品种代码映射为 yfinance 代码"""
        return self.SYMBOL_MAP.get(symbol.upper(), symbol)

    # ------------------------------------------------------------------
    # 公开异步接口
    # ------------------------------------------------------------------

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1d",
        limit: int = 200,
    ) -> list[dict]:
        """
        获取K线数据

        Returns:
            [{"open_time", "open_time_str", "open", "high", "low", "close",
              "volume", "close_time", "quote_volume", ...}]
        """
        yf_symbol = self._resolve_symbol(symbol)
        yf_interval = self.INTERVAL_MAP.get(interval, "1d")
        yf_period = self.PERIOD_MAP.get(interval, "2y")

        try:
            df = await asyncio.to_thread(
                self._download, yf_symbol, yf_period, yf_interval
            )
        except Exception as e:
            logger.error(f"Yahoo Finance download failed for {yf_symbol}: {e}")
            return []

        if df.empty:
            return []

        klines = []
        for idx, (ts, row) in enumerate(df.iterrows()):
            if len(klines) >= limit:
                break
            klines.append({
                "open_time": int(ts.timestamp() * 1000),
                "open_time_str": ts.strftime("%Y-%m-%d %H:%M"),
                "open":   round(float(row["Open"]),   4),
                "high":   round(float(row["High"]),   4),
                "low":    round(float(row["Low"]),     4),
                "close":  round(float(row["Close"]),   4),
                "volume": round(float(row["Volume"]),  2),
                "close_time": int(ts.timestamp() * 1000) + 3600000,
                "quote_volume": round(float(row["Close"]) * float(row["Volume"]), 2),
                "trades": 0,
            })

        return klines

    async def get_current_price(self, symbol: str) -> dict:
        """
        获取最新价格

        Returns:
            {"symbol", "price", "change", "change_pct", "time"}
        """
        yf_symbol = self._resolve_symbol(symbol)

        try:
            ticker = await asyncio.to_thread(yf.Ticker, yf_symbol)
            info = await asyncio.to_thread(lambda: ticker.info or {})

            price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
            prev = info.get("previousClose", price)
            change = price - prev if prev else 0
            change_pct = (change / prev * 100) if prev else 0

            return {
                "symbol": symbol,
                "yf_symbol": yf_symbol,
                "price": round(price, 4),
                "change": round(change, 4),
                "change_pct": round(change_pct, 2),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            logger.error(f"Yahoo Finance price failed for {yf_symbol}: {e}")
            return {"symbol": symbol, "price": 0, "error": str(e)}

    async def get_market_summary(self, symbol: str) -> dict:
        """
        获取市场综合数据（价格 + 24h变动 + 基本面）

        Returns:
            {"symbol", "price", "change_24h", "high", "low", "volume", ...}
        """
        yf_symbol = self._resolve_symbol(symbol)

        try:
            ticker = await asyncio.to_thread(yf.Ticker, yf_symbol)
            info = await asyncio.to_thread(lambda: ticker.info or {})

            price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
            prev = info.get("previousClose", price)
            change_pct = ((price - prev) / prev * 100) if prev else 0

            return {
                "symbol": symbol,
                "yf_symbol": yf_symbol,
                "price": round(price, 4),
                "change_24h": round(change_pct, 2),
                "high_24h": round(info.get("dayHigh", price), 4),
                "low_24h":  round(info.get("dayLow", price), 4),
                "volume_24h": round(info.get("volume", 0), 2),
                "market_cap": info.get("marketCap", 0),
                "fifty_two_week_high": round(info.get("fiftyTwoWeekHigh", 0), 4),
                "fifty_two_week_low":  round(info.get("fiftyTwoWeekLow", 0), 4),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            logger.error(f"Yahoo Finance summary failed for {yf_symbol}: {e}")
            return {"symbol": symbol, "price": 0, "error": str(e)}

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _download(self, symbol: str, period: str, interval: str):
        """同步下载（在 to_thread 中执行）"""
        tk = yf.Ticker(symbol)
        session_kwargs = {}
        if self.proxy:
            session_kwargs["proxy"] = self.proxy
        return tk.history(period=period, interval=interval, **session_kwargs)

    async def is_symbol_available(self, symbol: str) -> bool:
        """检查品种是否可用"""
        yf_symbol = self._resolve_symbol(symbol)
        try:
            ticker = await asyncio.to_thread(yf.Ticker, yf_symbol)
            info = await asyncio.to_thread(lambda: ticker.info or {})
            return bool(info.get("regularMarketPrice") or info.get("currentPrice"))
        except Exception:
            return False
