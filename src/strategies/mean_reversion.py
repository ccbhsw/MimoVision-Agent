"""
均值回归策略
基于布林带挤压/突破、RSI极端值的价格回归策略
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MeanReversionStrategy:
    """均值回归策略 - 布林带极端+RSI超买超卖+KDJ辅助"""

    def __init__(self, params: Optional[dict] = None):
        p = params or {}
        self.rsi_overbought = p.get("rsi_overbought", 70)
        self.rsi_oversold = p.get("rsi_oversold", 30)

    def generate_signal(self, indicators: dict) -> dict:
        reasons = []
        signal = "wait"
        strength = 0
        rsi = indicators.get("rsi", 50)
        bb_pos = indicators.get("bb_position", "middle")
        price = indicators.get("current_price", 0)
        bb_upper = indicators.get("bb_upper", 0)
        bb_lower = indicators.get("bb_lower", 0)
        bb_middle = indicators.get("bb_middle", 0)
        trend = indicators.get("trend", "ranging")
        kdj_j = indicators.get("kdj_j", 50)

        if bb_pos == "above_upper":
            reasons.append("突破布林带上轨，超买")
            signal = "short"
            strength += 25
        elif bb_pos == "below_lower":
            reasons.append("跌破布林带下轨，超卖")
            signal = "long"
            strength += 25

        if rsi > self.rsi_overbought:
            reasons.append(f"RSI={rsi}超买")
            signal = "short" if signal == "wait" else signal
            strength += 20
        elif rsi < self.rsi_oversold:
            reasons.append(f"RSI={rsi}超卖")
            signal = "long" if signal == "wait" else signal
            strength += 20

        if bb_upper > 0 and bb_lower > 0 and bb_middle > 0:
            width = (bb_upper - bb_lower) / bb_middle * 100
            if width < 2.0:
                reasons.append(f"布林带挤压({width:.1f}%)，突破在即")
                strength += 10

        if bb_middle > 0 and price > 0:
            dist = abs(price - bb_middle) / bb_middle * 100
            if dist > 3.0:
                reasons.append(f"偏离中轨{dist:.1f}%")
                strength += 10

        if signal == "long" and kdj_j < 20:
            reasons.append(f"KDJ-J={kdj_j}极度超卖")
            strength += 10
        elif signal == "short" and kdj_j > 80:
            reasons.append(f"KDJ-J={kdj_j}极度超买")
            strength += 10

        if trend in ("bullish", "bearish"):
            reasons.append(f"强趋势({trend})中均值回归风险高")
            strength -= 10

        strength = max(0, min(100, strength))
        if strength < 25:
            signal = "wait"
            reasons.append("信号不足")
        return {"signal": signal, "strength": strength, "reasons": reasons, "strategy": "mean_reversion"}

    def _check_bb_squeeze(self, indicators: dict) -> bool:
        bb_u = indicators.get("bb_upper", 0)
        bb_l = indicators.get("bb_lower", 0)
        bb_m = indicators.get("bb_middle", 0)
        return bb_m > 0 and (bb_u - bb_l) / bb_m * 100 < 2.0

    def _check_rsi_divergence(self, indicators: dict) -> str:
        rsi = indicators.get("rsi", 50)
        trend = indicators.get("trend", "ranging")
        if trend == "bullish" and rsi < 40:
            return "bullish_divergence"
        if trend == "bearish" and rsi > 60:
            return "bearish_divergence"
        return "none"

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
            if (sig["signal"] == "short" and pnl < 0) or (sig["signal"] == "long" and pnl > 0):
                wins += 1
        return wins / total if total > 0 else 0.5
