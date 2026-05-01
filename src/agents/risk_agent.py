"""
风险管理Agent
仓位计算、止损止盈、杠杆建议、综合风险评估
"""
import logging
from typing import Optional

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class RiskAgent:
    """
    风险管理Agent

    负责：
    - 基于ATR和账户余额的仓位计算
    - 止损止盈价位计算
    - 杠杆建议
    - 综合风险评估（0-100分）
    """

    def __init__(self):
        config = get_config()
        self.max_position_pct = config.risk.max_position_pct
        self.min_position_pct = config.risk.min_position_pct
        self.default_leverage = config.risk.default_leverage
        self.max_leverage = config.risk.max_leverage
        self.stop_loss_atr_mult = config.risk.stop_loss_atr_mult
        self.take_profit_atr_mult = config.risk.take_profit_atr_mult
        self.risk_per_trade_pct = config.risk.risk_per_trade_pct

    def calculate_position_size(
        self, account_balance: float, entry_price: float, stop_loss: float, risk_pct: Optional[float] = None,
    ) -> dict:
        """计算仓位大小"""
        risk_pct = risk_pct or self.risk_per_trade_pct
        risk_amount = account_balance * (risk_pct / 100)
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance == 0:
            stop_distance = entry_price * 0.01

        contracts = risk_amount / stop_distance
        position_value = contracts * entry_price
        leverage = self.default_leverage
        margin = position_value / leverage
        position_pct = (position_value / account_balance) * 100

        if position_pct > self.max_position_pct:
            position_pct = self.max_position_pct
            position_value = account_balance * (position_pct / 100)
            contracts = position_value / entry_price
            margin = position_value / leverage

        return {
            "contracts": round(contracts, 4), "margin": round(margin, 2),
            "position_value": round(position_value, 2), "position_pct": round(position_pct, 2),
            "actual_risk_pct": round(risk_pct, 2), "leverage": leverage,
        }

    def calculate_stop_levels(
        self, entry_price: float, direction: str, atr: float,
        support_levels: Optional[list[float]] = None, resistance_levels: Optional[list[float]] = None,
    ) -> dict:
        """计算止损止盈"""
        support_levels = support_levels or []
        resistance_levels = resistance_levels or []

        if direction == "long":
            atr_stop = entry_price - (atr * self.stop_loss_atr_mult)
            support_stop = min(support_levels) if support_levels else atr_stop
            stop_loss = min(atr_stop, support_stop)
            tp1 = entry_price + (atr * 1.5)
            tp2 = entry_price + (atr * self.take_profit_atr_mult)
            tp3 = entry_price + (atr * 6.0)
        else:
            atr_stop = entry_price + (atr * self.stop_loss_atr_mult)
            resistance_stop = max(resistance_levels) if resistance_levels else atr_stop
            stop_loss = max(atr_stop, resistance_stop)
            tp1 = entry_price - (atr * 1.5)
            tp2 = entry_price - (atr * self.take_profit_atr_mult)
            tp3 = entry_price - (atr * 6.0)

        risk = abs(entry_price - stop_loss)
        reward = abs(tp2 - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0

        return {
            "stop_loss": round(stop_loss, 4), "take_profit_1": round(tp1, 4),
            "take_profit_2": round(tp2, 4), "take_profit_3": round(tp3, 4),
            "risk_reward_ratio": round(rr_ratio, 2),
        }

    def suggest_leverage(self, atr_pct: float, account_balance: float, position_value: float) -> dict:
        """杠杆建议"""
        if atr_pct < 1.0:
            vol_level, base_lev = "low", 30
        elif atr_pct < 2.5:
            vol_level, base_lev = "medium", 20
        elif atr_pct < 5.0:
            vol_level, base_lev = "high", 10
        else:
            vol_level, base_lev = "extreme", 5

        max_safe = self.max_leverage
        if position_value > 0 and atr_pct > 0:
            max_safe = int((account_balance * 0.1) / (position_value * atr_pct / 100))
            max_safe = max(1, min(max_safe, self.max_leverage))

        reasons = {
            "low": "低波动率环境，可适当放大杠杆",
            "medium": "中等波动率，建议标准杠杆",
            "high": "高波动率，建议降低杠杆",
            "extreme": "极端波动率，强烈建议低杠杆",
        }

        return {
            "suggested_leverage": min(base_lev, max_safe),
            "volatility_level": vol_level,
            "max_safe_leverage": max_safe,
            "reason": reasons[vol_level],
        }

    def assess_risk(self, market_data: dict, indicators: dict, position_info: Optional[dict] = None) -> dict:
        """综合风险评估(0-100分)"""
        risk_score = 0

        atr_pct = indicators.get("atr_pct", 2.0)
        vol_risk = 30 if atr_pct > 5 else 20 if atr_pct > 3 else 10 if atr_pct > 1.5 else 5
        risk_score += vol_risk

        trend = indicators.get("trend", "ranging")
        trend_risk = 20 if trend == "ranging" else 8
        risk_score += trend_risk

        rsi = indicators.get("rsi", 50)
        rsi_risk = 18 if rsi > 75 or rsi < 25 else 10 if rsi > 65 or rsi < 35 else 5
        risk_score += rsi_risk

        funding_rate = abs(market_data.get("funding_rate", 0))
        funding_risk = 12 if funding_rate > 0.001 else 7 if funding_rate > 0.0005 else 3
        risk_score += funding_risk

        volume_ratio = indicators.get("volume_ratio", 1.0)
        volume_risk = 8 if volume_ratio > 2.0 else 5 if volume_ratio > 1.5 else 2
        risk_score += volume_risk

        risk_score = min(risk_score, 100)
        level = "low" if risk_score <= 30 else "medium" if risk_score <= 60 else "high"

        return {
            "risk_score": risk_score, "overall_level": level,
            "volatility_risk": vol_risk, "trend_risk": trend_risk,
            "rsi_risk": rsi_risk, "funding_risk": funding_risk, "volume_risk": volume_risk,
        }

    def calculate_drawdown(self, entry_price: float, current_price: float, leverage: int, direction: str) -> float:
        """计算当前回撤百分比"""
        if direction == "long":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        return round(-pnl_pct * leverage * 100, 2)
