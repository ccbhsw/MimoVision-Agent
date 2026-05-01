"""
杠杆建议引擎
基于波动率、账户规模、相关性风险的杠杆建议
"""
import logging

logger = logging.getLogger(__name__)


class LeverageAdvisor:
    """杠杆建议引擎"""

    def __init__(self, max_leverage: int = 50, max_loss_pct: float = 10.0):
        self.max_leverage = max_leverage
        self.max_loss_pct = max_loss_pct

    def suggest(
        self,
        atr_pct: float,
        account_balance: float,
        position_value: float,
    ) -> dict:
        """
        杠杆建议

        Args:
            atr_pct: ATR百分比(ATR/价格*100)
            account_balance: 账户余额
            position_value: 仓位价值

        Returns:
            {suggested_leverage, volatility_level, max_safe_leverage, reason}
        """
        vol_level = self._assess_volatility(atr_pct)

        vol_leverage_map = {
            "low": 30,
            "medium": 20,
            "high": 10,
            "extreme": 5,
        }
        base_leverage = vol_leverage_map.get(vol_level, 20)

        max_safe = self._calculate_max_safe_leverage(
            account_balance, position_value, atr_pct
        )

        suggested = min(base_leverage, max_safe, self.max_leverage)

        reasons = {
            "low": "低波动率环境，可适当放大杠杆",
            "medium": "中等波动率，建议标准杠杆",
            "high": "高波动率，建议降低杠杆控制风险",
            "extreme": "极端波动率，强烈建议低杠杆或观望",
        }

        return {
            "suggested_leverage": suggested,
            "volatility_level": vol_level,
            "max_safe_leverage": max_safe,
            "reason": reasons[vol_level],
        }

    def _assess_volatility(self, atr_pct: float) -> str:
        """评估波动率等级"""
        if atr_pct < 1.0:
            return "low"
        elif atr_pct < 2.5:
            return "medium"
        elif atr_pct < 5.0:
            return "high"
        return "extreme"

    def _calculate_max_safe_leverage(
        self,
        account_balance: float,
        position_value: float,
        atr_pct: float,
    ) -> int:
        """
        计算最大安全杠杆

        确保单次最大亏损不超过账户余额的max_loss_pct%
        """
        if position_value == 0 or atr_pct == 0:
            return self.max_leverage

        max_loss_amount = account_balance * (self.max_loss_pct / 100)
        # 假设最坏情况：价格波动1个ATR
        max_leverage = int(max_loss_amount / (position_value * atr_pct / 100))
        return max(1, min(max_leverage, self.max_leverage))

    def adjust_for_correlation(
        self,
        leverage: int,
        correlated_positions: int = 0,
    ) -> int:
        """
        相关性调整

        如果持有多个相关品种，降低总杠杆

        Args:
            leverage: 当前建议杠杆
            correlated_positions: 已持有的相关仓位数

        Returns:
            调整后的杠杆
        """
        if correlated_positions <= 0:
            return leverage

        # 每多一个相关仓位，杠杆降低20%
        adjustment = 0.8 ** correlated_positions
        adjusted = int(leverage * adjustment)
        return max(1, adjusted)
