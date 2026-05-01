"""
突破策略
基于区间突破、放量确认、支撑阻力突破的交易策略
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BreakoutStrategy:
    """突破策略 - 支撑阻力突破+放量确认+布林带突破"""

    def __init__(self, params: Optional[dict] = None):
        p = params or {}
        self.volume_threshold = p.get("volume_threshold", 1.5)
        self.atr_multiplier = p.get("atr_multiplier", 1.5)

    def generate_signal(self, indicators: dict) -> dict:
        reasons = []
        signal = "wait"
        strength = 0
        price = indicators.get("current_price", 0)
        atr_pct = indicators.get("atr_pct", 2.0)
        volume_ratio = indicators.get("volume_ratio", 1.0)
        supports = indicators.get("support_levels", [])
        resistances = indicators.get("resistance_levels", [])
        bb_pos = indicators.get("bb_position", "middle")
        trend = indicators.get("trend", "ranging")
        macd_hist = indicators.get("macd_histogram", 0)

        # 1. 支撑阻力突破
        for res in resistances:
            if res > 0 and price > res and price < res * 1.01:
                reasons.append(f"价格突破阻力位${res:.2f}")
                signal = "long"
                strength += 25
                break
        for sup in supports:
            if sup > 0 and price < sup and price > sup * 0.99:
                reasons.append(f"价格跌破支撑位${sup:.2f}")
                signal = "short"
                strength += 25
                break

        # 2. 布林带突破
        if bb_pos == "above_upper":
            reasons.append("突破布林带上轨")
            if signal == "wait":
                signal = "long"
            strength += 15
        elif bb_pos == "below_lower":
            reasons.append("跌破布林带下轨")
            if signal == "wait":
                signal = "short"
            strength += 15

        # 3. 成交量确认
        if volume_ratio > self.volume_threshold:
            reasons.append(f"成交量放大{volume_ratio:.1f}x确认突破")
            strength += 20
        else:
            reasons.append(f"成交量不足({volume_ratio:.1f}x)")
            strength -= 5

        # 4. 波动率
        if atr_pct > 3.0:
            reasons.append(f"ATR{atr_pct:.1f}%波动率放大")
            strength += 10
        elif atr_pct < 1.0:
            reasons.append("波动率偏低")
            strength -= 10

        # 5. 趋势方向
        if trend == "bullish" and signal == "long":
            reasons.append("多头趋势中向上突破可靠")
            strength += 10
        elif trend == "bearish" and signal == "short":
            reasons.append("空头趋势中向下突破可靠")
            strength += 10

        # 6. MACD动能
        if signal == "long" and macd_hist > 0:
            reasons.append("MACD多头动能确认")
            strength += 8
        elif signal == "short" and macd_hist < 0:
            reasons.append("MACD空头动能确认")
            strength += 8

        strength = max(0, min(100, strength))
        if strength < 30:
            signal = "wait"
            reasons.append("突破信号强度不足")
        return {"signal": signal, "strength": strength, "reasons": reasons, "strategy": "breakout"}

    def _check_range_breakout(self, indicators: dict) -> str:
        supports = indicators.get("support_levels", [])
        resistances = indicators.get("resistance_levels", [])
        price = indicators.get("current_price", 0)
        if not supports or not resistances or price == 0:
            return "none"
        if price > max(resistances):
            return "upward_breakout"
        elif price < min(supports):
            return "downward_breakout"
        return "within_range"

    def _check_volume_breakout(self, indicators: dict) -> bool:
        return indicators.get("volume_ratio", 1.0) > self.volume_threshold

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
