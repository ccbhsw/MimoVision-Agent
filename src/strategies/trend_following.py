"""
趋势跟踪策略
基于EMA交叉、MACD信号、成交量确认的趋势跟踪系统
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TrendFollowingStrategy:
    """趋势跟踪策略 - EMA排列+MACD交叉+成交量确认"""

    def __init__(self, params: Optional[dict] = None):
        p = params or {}
        self.ema_fast = p.get("ema_fast", 9)
        self.ema_slow = p.get("ema_slow", 21)
        self.rsi_overbought = p.get("rsi_overbought", 70)
        self.rsi_oversold = p.get("rsi_oversold", 30)
        self.volume_threshold = p.get("volume_threshold", 1.2)
        self.atr_multiplier = p.get("atr_multiplier", 2.0)

    def generate_signal(self, indicators: dict) -> dict:
        reasons = []
        signal = "wait"
        strength = 0
        trend = indicators.get("trend", "ranging")
        rsi = indicators.get("rsi", 50)
        volume_ratio = indicators.get("volume_ratio", 1.0)

        if trend == "bullish":
            reasons.append("EMA多头排列(9>21>50)")
            signal = "long"
            strength += 30
        elif trend == "bearish":
            reasons.append("EMA空头排列(9<21<50)")
            signal = "short"
            strength += 30

        macd_cross = indicators.get("macd_cross", "none")
        if macd_cross == "bullish":
            reasons.append("MACD金叉确认")
            strength += 25
        elif macd_cross == "bearish":
            reasons.append("MACD死叉确认")
            strength += 25

        if signal == "long" and rsi > self.rsi_overbought:
            reasons.append(f"RSI={rsi}超买区，减弱信号")
            strength -= 15
        elif signal == "short" and rsi < self.rsi_oversold:
            reasons.append(f"RSI={rsi}超卖区，减弱信号")
            strength -= 15

        if volume_ratio > self.volume_threshold:
            reasons.append(f"成交量放大{volume_ratio:.1f}x确认")
            strength += 15

        bb_pos = indicators.get("bb_position", "middle")
        if signal == "long" and bb_pos == "below_lower":
            reasons.append("布林带下轨支撑")
            strength += 5
        elif signal == "short" and bb_pos == "above_upper":
            reasons.append("布林带上轨压力")
            strength += 5

        strength = max(0, min(100, strength))
        if strength < 30:
            signal = "wait"
            reasons.append("信号强度不足")
        return {"signal": signal, "strength": strength, "reasons": reasons, "strategy": "trend_following"}

    def _check_ema_crossover(self, indicators: dict) -> str:
        mc = indicators.get("macd_cross", "none")
        if mc == "bullish":
            return "golden_cross"
        if mc == "bearish":
            return "death_cross"
        return "no_cross"

    def _check_volume_confirmation(self, indicators: dict) -> bool:
        return indicators.get("volume_ratio", 1.0) > self.volume_threshold

    def _calculate_entry_exit(self, price: float, direction: str, atr: float) -> dict:
        if direction == "long":
            stop = price - atr * self.atr_multiplier
            tp1, tp2 = price + atr * 1.5, price + atr * 3.0
        else:
            stop = price + atr * self.atr_multiplier
            tp1, tp2 = price - atr * 1.5, price - atr * 3.0
        return {"entry": round(price, 4), "stop_loss": round(stop, 4),
                "take_profit_1": round(tp1, 4), "take_profit_2": round(tp2, 4)}

    def validate(self, indicators_list: list[dict]) -> float:
        if len(indicators_list) < 10:
            return 0.5
        wins, total = 0, 0
        for i in range(1, len(indicators_list)):
            sig = self.generate_signal(indicators_list[i - 1])
            if sig["signal"] == "wait":
                continue
            pp = indicators_list[i - 1].get("current_price", 0)
            cp = indicators_list[i].get("current_price", 0)
            if pp == 0:
                continue
            total += 1
            pnl = (cp - pp) / pp
            if (sig["signal"] == "long" and pnl > 0) or (sig["signal"] == "short" and pnl < 0):
                wins += 1
        return wins / total if total > 0 else 0.5
