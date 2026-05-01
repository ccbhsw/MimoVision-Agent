"""
仓位计算器
支持固定比例、凯利公式、波动率调整等多种仓位计算方法
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PositionSizer:
    """仓位计算器"""

    def __init__(self, max_position_pct: float = 15.0, max_leverage: int = 50):
        self.max_position_pct = max_position_pct
        self.max_leverage = max_leverage

    def fixed_fractional(
        self,
        balance: float,
        risk_pct: float,
        entry: float,
        stop_loss: float,
        leverage: int = 20,
    ) -> dict:
        """
        固定比例仓位计算

        Args:
            balance: 账户余额(USDT)
            risk_pct: 单笔风险百分比
            entry: 入场价
            stop_loss: 止损价
            leverage: 杠杆

        Returns:
            {contracts, margin, position_value, position_pct, risk_amount}
        """
        risk_amount = balance * (risk_pct / 100)
        stop_distance = abs(entry - stop_loss)
        if stop_distance == 0:
            stop_distance = entry * 0.01

        contracts = risk_amount / stop_distance
        position_value = contracts * entry
        margin = position_value / leverage
        position_pct = (position_value / balance) * 100 if balance > 0 else 0

        # 限制仓位
        if position_pct > self.max_position_pct:
            position_pct = self.max_position_pct
            position_value = balance * (position_pct / 100)
            contracts = position_value / entry if entry > 0 else 0
            margin = position_value / leverage

        return {
            "contracts": round(contracts, 4),
            "margin": round(margin, 2),
            "position_value": round(position_value, 2),
            "position_pct": round(position_pct, 2),
            "risk_amount": round(risk_amount, 2),
            "leverage": leverage,
        }

    def kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        balance: float,
        leverage: int = 20,
        fraction: float = 0.25,
    ) -> dict:
        """
        凯利公式仓位计算（1/4 Kelly保守版本）

        Args:
            win_rate: 胜率(0-1)
            avg_win: 平均盈利百分比
            avg_loss: 平均亏损百分比
            balance: 账户余额
            leverage: 杠杆
            fraction: Kelly比例（0.25=1/4 Kelly）

        Returns:
            {kelly_pct, adjusted_pct, position_value, margin}
        """
        if avg_loss == 0 or win_rate == 0:
            return {"kelly_pct": 0, "adjusted_pct": 0, "position_value": 0, "margin": 0}

        win_loss_ratio = avg_win / avg_loss
        kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        kelly = max(0, kelly)

        adjusted = kelly * fraction * 100  # 转百分比
        adjusted = min(adjusted, self.max_position_pct)

        position_value = balance * (adjusted / 100)
        margin = position_value / leverage

        return {
            "kelly_pct": round(kelly * 100, 2),
            "adjusted_pct": round(adjusted, 2),
            "position_value": round(position_value, 2),
            "margin": round(margin, 2),
            "leverage": leverage,
        }

    def volatility_adjusted(
        self,
        balance: float,
        atr: float,
        price: float,
        target_risk: float = 2.0,
        leverage: int = 20,
    ) -> dict:
        """
        波动率调整仓位

        Args:
            balance: 账户余额
            atr: ATR值
            price: 当前价格
            target_risk: 目标风险百分比
            leverage: 杠杆

        Returns:
            {contracts, margin, position_value, position_pct, vol_adjusted_risk}
        """
        if price == 0 or atr == 0:
            return {"contracts": 0, "margin": 0, "position_value": 0, "position_pct": 0, "vol_adjusted_risk": 0}

        # ATR作为止损距离
        risk_amount = balance * (target_risk / 100)
        contracts = risk_amount / (atr * 2)  # 2倍ATR止损
        position_value = contracts * price
        margin = position_value / leverage
        position_pct = (position_value / balance) * 100 if balance > 0 else 0

        position_pct = min(position_pct, self.max_position_pct)

        return {
            "contracts": round(contracts, 4),
            "margin": round(margin, 2),
            "position_value": round(position_value, 2),
            "position_pct": round(position_pct, 2),
            "vol_adjusted_risk": round(target_risk, 2),
            "leverage": leverage,
        }

    def calculate_margin(self, position_value: float, leverage: int) -> dict:
        """计算保证金"""
        margin = position_value / leverage if leverage > 0 else position_value
        return {
            "position_value": round(position_value, 2),
            "margin": round(margin, 2),
            "leverage": leverage,
        }
