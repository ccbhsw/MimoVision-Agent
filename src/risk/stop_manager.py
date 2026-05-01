"""
止损止盈管理
ATR止损、支撑阻力止损、移动止损、保本止损
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StopManager:
    """止损止盈管理器"""

    def __init__(self, atr_mult_sl: float = 2.5, atr_mult_tp: float = 4.0):
        self.atr_mult_sl = atr_mult_sl
        self.atr_mult_tp = atr_mult_tp

    def atr_based_stop(
        self,
        entry: float,
        direction: str,
        atr: float,
        multiplier: Optional[float] = None,
    ) -> dict:
        """
        ATR止损止盈

        Args:
            entry: 入场价格
            direction: long/short
            atr: ATR值
            multiplier: ATR倍数（默认用配置）

        Returns:
            {stop_loss, take_profit_1, take_profit_2, take_profit_3, risk_reward_ratio}
        """
        mult = multiplier or self.atr_mult_sl
        tp_mult = self.atr_mult_tp

        if direction == "long":
            stop = entry - atr * mult
            tp1 = entry + atr * 1.5
            tp2 = entry + atr * tp_mult
            tp3 = entry + atr * 6.0
        else:
            stop = entry + atr * mult
            tp1 = entry - atr * 1.5
            tp2 = entry - atr * tp_mult
            tp3 = entry - atr * 6.0

        risk = abs(entry - stop)
        reward = abs(tp2 - entry)
        rr = reward / risk if risk > 0 else 0

        return {
            "stop_loss": round(stop, 4),
            "take_profit_1": round(tp1, 4),
            "take_profit_2": round(tp2, 4),
            "take_profit_3": round(tp3, 4),
            "risk_reward_ratio": round(rr, 2),
            "risk_amount": round(risk, 4),
        }

    def support_resistance_stop(
        self,
        entry: float,
        direction: str,
        support_levels: list[float],
        resistance_levels: list[float],
        buffer_pct: float = 0.3,
    ) -> dict:
        """
        基于支撑阻力的止损

        Args:
            entry: 入场价格
            direction: long/short
            support_levels: 支撑位列表
            resistance_levels: 阻力位列表
            buffer_pct: 缓冲百分比

        Returns:
            {stop_loss, key_level, buffer}
        """
        buffer = entry * (buffer_pct / 100)

        if direction == "long":
            if support_levels:
                stop = min(support_levels) - buffer
                key_level = min(support_levels)
            else:
                stop = entry * 0.97
                key_level = entry * 0.97
        else:
            if resistance_levels:
                stop = max(resistance_levels) + buffer
                key_level = max(resistance_levels)
            else:
                stop = entry * 1.03
                key_level = entry * 1.03

        return {
            "stop_loss": round(stop, 4),
            "key_level": round(key_level, 4),
            "buffer": round(buffer, 4),
        }

    def trailing_stop(
        self,
        entry: float,
        direction: str,
        atr: float,
        activation_pct: float = 1.0,
    ) -> dict:
        """
        移动止损

        Args:
            entry: 入场价
            direction: long/short
            atr: ATR值
            activation_pct: 激活百分比（盈利多少开始移动止损）

        Returns:
            {activation_price, initial_stop, trailing_distance}
        """
        trailing_distance = atr * 2.0

        if direction == "long":
            activation_price = entry * (1 + activation_pct / 100)
            initial_stop = entry - atr * self.atr_mult_sl
        else:
            activation_price = entry * (1 - activation_pct / 100)
            initial_stop = entry + atr * self.atr_mult_sl

        return {
            "activation_price": round(activation_price, 4),
            "initial_stop": round(initial_stop, 4),
            "trailing_distance": round(trailing_distance, 4),
        }

    def breakeven_stop(
        self,
        entry: float,
        direction: str,
        current_price: float,
        activation_pct: float = 1.5,
    ) -> dict:
        """
        保本止损

        Returns:
            {should_activate, activation_price, breakeven_stop}
        """
        if direction == "long":
            activation_price = entry * (1 + activation_pct / 100)
            should_activate = current_price >= activation_price
            be_stop = entry * 1.001  # 略高于入场价
        else:
            activation_price = entry * (1 - activation_pct / 100)
            should_activate = current_price <= activation_price
            be_stop = entry * 0.999

        return {
            "should_activate": should_activate,
            "activation_price": round(activation_price, 4),
            "breakeven_stop": round(be_stop, 4),
        }

    def calculate_risk_reward(
        self,
        entry: float,
        stop_loss: float,
        take_profit: float,
    ) -> dict:
        """计算风险回报比"""
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        rr = reward / risk if risk > 0 else 0

        return {
            "risk": round(risk, 4),
            "reward": round(reward, 4),
            "risk_reward_ratio": round(rr, 2),
            "is_favorable": rr >= 2.0,
        }
