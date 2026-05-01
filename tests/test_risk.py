"""
测试模块 - 风控组件
测试 PositionSizer、StopManager、LeverageAdvisor
"""
import pytest

from src.risk.position_sizer import PositionSizer
from src.risk.stop_manager import StopManager
from src.risk.leverage_advisor import LeverageAdvisor


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sizer():
    return PositionSizer(max_position_pct=15.0, max_leverage=50)


@pytest.fixture
def stop_mgr():
    return StopManager(atr_mult_sl=2.5, atr_mult_tp=4.0)


@pytest.fixture
def lev_advisor():
    return LeverageAdvisor(max_leverage=50, max_loss_pct=10.0)


# ── PositionSizer Tests ──────────────────────────────────────────

class TestPositionSizer:
    """仓位计算器测试"""

    def test_fixed_fractional_basic(self, sizer):
        result = sizer.fixed_fractional(
            balance=10000, risk_pct=2.0, entry=50000, stop_loss=49000, leverage=20
        )
        assert result["contracts"] > 0
        assert result["margin"] > 0
        assert result["position_pct"] <= 15.0
        assert result["leverage"] == 20

    def test_fixed_fractional_max_cap(self, sizer):
        """仓位不超过上限"""
        result = sizer.fixed_fractional(
            balance=100000, risk_pct=10.0, entry=50000, stop_loss=49999, leverage=10
        )
        assert result["position_pct"] <= 15.0

    def test_kelly_criterion(self, sizer):
        result = sizer.kelly_criterion(
            win_rate=0.6, avg_win=3.0, avg_loss=1.5, balance=10000, leverage=20
        )
        assert result["kelly_pct"] > 0
        assert result["adjusted_pct"] > 0
        assert result["position_value"] > 0

    def test_kelly_zero_loss(self, sizer):
        """avg_loss=0 时返回安全结果"""
        result = sizer.kelly_criterion(
            win_rate=0.6, avg_win=3.0, avg_loss=0, balance=10000
        )
        assert result["kelly_pct"] == 0

    def test_volatility_adjusted(self, sizer):
        result = sizer.volatility_adjusted(
            balance=10000, atr=500, price=50000, target_risk=2.0, leverage=20
        )
        assert result["contracts"] > 0
        assert result["position_pct"] <= 15.0

    def test_volatility_zero_price(self, sizer):
        """价格为0时返回安全结果"""
        result = sizer.volatility_adjusted(
            balance=10000, atr=500, price=0, leverage=20
        )
        assert result["contracts"] == 0


# ── StopManager Tests ────────────────────────────────────────────

class TestStopManager:
    """止损止盈管理器测试"""

    def test_atr_stop_long(self, stop_mgr):
        result = stop_mgr.atr_based_stop(entry=50000, direction="long", atr=1000)
        assert result["stop_loss"] < 50000
        assert result["take_profit_1"] > 50000
        assert result["take_profit_2"] > result["take_profit_1"]
        assert result["risk_reward_ratio"] > 0

    def test_atr_stop_short(self, stop_mgr):
        result = stop_mgr.atr_based_stop(entry=50000, direction="short", atr=1000)
        assert result["stop_loss"] > 50000
        assert result["take_profit_1"] < 50000
        assert result["take_profit_2"] < result["take_profit_1"]

    def test_support_resistance_stop_long(self, stop_mgr):
        result = stop_mgr.support_resistance_stop(
            entry=50000, direction="long",
            support_levels=[49000, 48500], resistance_levels=[51000]
        )
        assert result["stop_loss"] < 49000
        assert result["key_level"] == 48500

    def test_support_resistance_stop_short(self, stop_mgr):
        result = stop_mgr.support_resistance_stop(
            entry=50000, direction="short",
            support_levels=[49000], resistance_levels=[51000, 51500]
        )
        assert result["stop_loss"] > 51500
        assert result["key_level"] == 51500

    def test_trailing_stop(self, stop_mgr):
        result = stop_mgr.trailing_stop(entry=50000, direction="long", atr=1000)
        assert result["activation_price"] > 50000
        assert result["initial_stop"] < 50000
        assert result["trailing_distance"] > 0

    def test_breakeven_stop_long(self, stop_mgr):
        result = stop_mgr.breakeven_stop(
            entry=50000, direction="long", current_price=51000
        )
        assert result["should_activate"] is True
        assert result["breakeven_stop"] >= 50000

    def test_breakeven_not_activated(self, stop_mgr):
        result = stop_mgr.breakeven_stop(
            entry=50000, direction="long", current_price=50500
        )
        assert result["should_activate"] is False

    def test_risk_reward_favorable(self, stop_mgr):
        result = stop_mgr.calculate_risk_reward(
            entry=50000, stop_loss=49000, take_profit=52000
        )
        assert result["risk_reward_ratio"] == 2.0
        assert result["is_favorable"] is True

    def test_risk_reward_unfavorable(self, stop_mgr):
        result = stop_mgr.calculate_risk_reward(
            entry=50000, stop_loss=49000, take_profit=50500
        )
        assert result["is_favorable"] is False


# ── LeverageAdvisor Tests ────────────────────────────────────────

class TestLeverageAdvisor:
    """杠杆建议引擎测试"""

    def test_low_volatility(self, lev_advisor):
        result = lev_advisor.suggest(
            atr_pct=0.5, account_balance=10000, position_value=5000
        )
        assert result["volatility_level"] == "low"
        assert result["suggested_leverage"] >= 20

    def test_high_volatility(self, lev_advisor):
        result = lev_advisor.suggest(
            atr_pct=4.0, account_balance=10000, position_value=5000
        )
        assert result["volatility_level"] == "high"
        assert result["suggested_leverage"] <= 15

    def test_extreme_volatility(self, lev_advisor):
        result = lev_advisor.suggest(
            atr_pct=8.0, account_balance=10000, position_value=5000
        )
        assert result["volatility_level"] == "extreme"
        assert result["suggested_leverage"] <= 10

    def test_max_leverage_cap(self, lev_advisor):
        result = lev_advisor.suggest(
            atr_pct=0.3, account_balance=100000, position_value=1000
        )
        assert result["suggested_leverage"] <= 50

    def test_correlation_adjustment(self, lev_advisor):
        base = 20
        adj1 = lev_advisor.adjust_for_correlation(base, correlated_positions=1)
        adj2 = lev_advisor.adjust_for_correlation(base, correlated_positions=3)
        assert adj1 < base
        assert adj2 < adj1

    def test_no_correlation(self, lev_advisor):
        result = lev_advisor.adjust_for_correlation(20, correlated_positions=0)
        assert result == 20
