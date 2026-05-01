"""
市场综合指标模块
资金费率趋势、爆仓估算、大户活跃度、市场广度
依赖 BinanceFuturesCollector 提供的底层数据
"""
import logging
from typing import Optional
from datetime import datetime

from src.data_collectors.binance_futures import BinanceFuturesCollector

logger = logging.getLogger(__name__)


class MarketMetricsCollector:
    """市场综合指标采集器"""

    def __init__(self, binance: BinanceFuturesCollector):
        self.binance = binance

    # ------------------------------------------------------------------
    # 资金费率趋势
    # ------------------------------------------------------------------

    async def funding_rate_trend(self, symbol: str, limit: int = 30) -> dict:
        """
        分析资金费率趋势

        Returns:
            {"current", "avg_7d", "avg_30d", "trend", "interpretation"}
        """
        data = await self.binance.get_funding_rate(symbol, limit=limit)
        if not data:
            return {"current": 0, "avg_7d": 0, "avg_30d": 0, "trend": "neutral"}

        rates = [d["funding_rate"] for d in data]
        current = rates[-1]
        avg_7d  = sum(rates[-7:]) / len(rates[-7:]) if len(rates) >= 7 else sum(rates) / len(rates)
        avg_30d = sum(rates) / len(rates)

        # 趋势判断：最近7天 vs 之前
        if len(rates) >= 14:
            recent_avg = sum(rates[-7:]) / 7
            older_avg  = sum(rates[-14:-7]) / 7
            if recent_avg > older_avg * 1.5 and recent_avg > 0.0003:
                trend = "rising_positive"
            elif recent_avg < older_avg * 0.5 and recent_avg < -0.0003:
                trend = "rising_negative"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        interpretation = self._interpret_funding(current)

        return {
            "current": round(current, 6),
            "avg_7d":  round(avg_7d, 6),
            "avg_30d": round(avg_30d, 6),
            "trend": trend,
            "interpretation": interpretation,
            "data_points": len(rates),
        }

    # ------------------------------------------------------------------
    # 爆仓估算
    # ------------------------------------------------------------------

    async def liquidation_estimate(
        self,
        symbol: str,
        price: float,
        atr_pct: float,
    ) -> dict:
        """
        基于当前价格和波动率估算各杠杆倍数的爆仓价位

        Returns:
            {"leverage_levels": [{leverage, long_liq, short_liq, distance_pct}]}
        """
        levels = []
        for lev in [5, 10, 20, 25, 50, 75, 100, 125]:
            margin_pct = 100 / lev
            # 简化估算：爆仓距离 ≈ 维持保证金率 + buffer
            buffer = atr_pct * 0.5  # 半个ATR的buffer
            distance = margin_pct + buffer

            long_liq  = round(price * (1 - distance / 100), 4)
            short_liq = round(price * (1 + distance / 100), 4)

            levels.append({
                "leverage": lev,
                "long_liquidation": long_liq,
                "short_liquidation": short_liq,
                "distance_pct": round(distance, 2),
            })

        return {
            "symbol": symbol,
            "price": price,
            "atr_pct": atr_pct,
            "leverage_levels": levels,
        }

    # ------------------------------------------------------------------
    # 大户活跃度
    # ------------------------------------------------------------------

    async def whale_activity(self, symbol: str) -> dict:
        """
        分析大户行为

        Returns:
            {"long_pct", "short_pct", "ratio", "bias", "global_ratio"}
        """
        top_ratio   = await self.binance.get_long_short_ratio(symbol, limit=1)
        global_ratio = await self.binance.get_global_long_short_ratio(symbol, limit=1)

        top = top_ratio[0] if top_ratio else {}
        glb = global_ratio[0] if global_ratio else {}

        long_pct  = top.get("long_pct", 0.5)
        short_pct = top.get("short_pct", 0.5)
        ratio     = top.get("long_short_ratio", 1.0)
        g_ratio   = glb.get("long_short_ratio", 1.0)

        if ratio > 1.3:
            bias = "bullish"
        elif ratio < 0.77:
            bias = "bearish"
        else:
            bias = "neutral"

        return {
            "long_pct": round(long_pct, 4),
            "short_pct": round(short_pct, 4),
            "ratio": round(ratio, 4),
            "bias": bias,
            "global_ratio": round(g_ratio, 4),
            "divergence": abs(ratio - g_ratio) > 0.3,
        }

    # ------------------------------------------------------------------
    # 市场广度
    # ------------------------------------------------------------------

    async def market_breadth(self, symbols: list[str] = None) -> dict:
        """
        计算市场广度（多空比加权）

        Args:
            symbols: 要检查的品种列表

        Returns:
            {"total", "bullish", "bearish", "neutral", "breadth_score"}
        """
        if not symbols:
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

        bullish, bearish, neutral = 0, 0, 0
        for sym in symbols:
            try:
                ticker = await self.binance.get_24h_ticker(sym)
                pct = ticker.get("price_change_pct", 0)
                if pct > 1.0:
                    bullish += 1
                elif pct < -1.0:
                    bearish += 1
                else:
                    neutral += 1
            except Exception as e:
                logger.warning(f"Market breadth check failed for {sym}: {e}")
                neutral += 1

        total = len(symbols)
        breadth_score = (bullish - bearish) / total if total else 0

        return {
            "total": total,
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "breadth_score": round(breadth_score, 2),
        }

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _interpret_funding(rate: float) -> str:
        """解读资金费率含义"""
        if rate > 0.001:
            return "极度多头拥挤，短期可能回调"
        elif rate > 0.0003:
            return "温和多头，市场偏多"
        elif rate > -0.0003:
            return "资金费率中性"
        elif rate > -0.001:
            return "温和空头，市场偏空"
        else:
            return "极度空头拥挤，短期可能反弹"
