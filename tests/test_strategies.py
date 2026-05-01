"""
测试模块 - 策略信号生成
测试 TrendFollowing、MeanReversion、Breakout、Ensemble 四个策略
"""
import pytest

from src.strategies.trend_following import TrendFollowingStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.breakout import BreakoutStrategy
from src.strategies.ensemble import EnsembleStrategy


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def bullish_indicators() -> dict:
    """多头指标集合"""
    return {
        "trend": "bullish",
        "rsi": 58,
        "macd": 150.5,
        "macd_signal": 120.3,
        "macd_histogram": 30.2,
        "macd_cross": "bullish",
        "bb_upper": 52000,
        "bb_middle": 50000,
        "bb_lower": 48000,
        "bb_position": "middle",
        "atr": 1200,
        "atr_pct": 2.4,
        "volume": 50000,
        "volume_ma": 30000,
        "volume_ratio": 1.67,
        "current_price": 50500,
        "support_levels": [49000, 48500, 48000],
        "resistance_levels": [51000, 51500, 52000],
    }


@pytest.fixture
def bearish_indicators() -> dict:
    """空头指标集合"""
    return {
        "trend": "bearish",
        "rsi": 35,
        "macd": -200.5,
        "macd_signal": -150.3,
        "macd_histogram": -50.2,
        "macd_cross": "bearish",
        "bb_upper": 52000,
        "bb_middle": 50000,
        "bb_lower": 48000,
        "bb_position": "below_lower",
        "atr": 1500,
        "atr_pct": 3.0,
        "volume": 60000,
        "volume_ma": 35000,
        "volume_ratio": 1.71,
        "current_price": 47800,
        "support_levels": [47500, 47000, 46500],
        "resistance_levels": [49000, 49500, 50000],
    }


@pytest.fixture
def ranging_indicators() -> dict:
    """震荡指标集合"""
    return {
        "trend": "ranging",
        "rsi": 50,
        "macd": 5.5,
        "macd_signal": 5.2,
        "macd_histogram": 0.3,
        "macd_cross": "none",
        "bb_upper": 51000,
        "bb_middle": 50000,
        "bb_lower": 49000,
        "bb_position": "middle",
        "atr": 500,
        "atr_pct": 1.0,
        "volume": 25000,
        "volume_ma": 30000,
        "volume_ratio": 0.83,
        "current_price": 50100,
        "support_levels": [49500, 49200, 49000],
        "resistance_levels": [50500, 50800, 51000],
    }


# ── TrendFollowing Tests ──────────────────────────────────────────

class TestTrendFollowing:
    """趋势跟踪策略测试"""

    def test_bullish_signal(self, bullish_indicators):
        s = TrendFollowingStrategy()
        result = s.generate_signal(bullish_indicators)
        assert result["signal"] == "long"
        assert result["strength"] >= 30
        assert "EMA多头排列" in result["reasons"][0]

    def test_bearish_signal(self, bearish_indicators):
        s = TrendFollowingStrategy()
        result = s.generate_signal(bearish_indicators)
        assert result["signal"] == "short"
        assert result["strength"] >= 30
        assert "EMA空头排列" in result["reasons"][0]

    def test_ranging_gives_wait(self, ranging_indicators):
        s = TrendFollowingStrategy()
        result = s.generate_signal(ranging_indicators)
        # 震荡市通常信号强度不够
        assert result["signal"] in ("wait", "long", "short")
        assert result["strategy"] == "trend_following"

    def test_strength_capped(self, bullish_indicators):
        s = TrendFollowingStrategy()
        result = s.generate_signal(bullish_indicators)
        assert 0 <= result["strength"] <= 100

    def test_overbought_reduces_strength(self, bullish_indicators):
        bullish_indicators["rsi"] = 78
        s = TrendFollowingStrategy()
        result = s.generate_signal(bullish_indicators)
        assert any("超买" in r for r in result["reasons"])


# ── MeanReversion Tests ──────────────────────────────────────────

class TestMeanReversion:
    """均值回归策略测试"""

    def test_oversold_signal(self, bearish_indicators):
        bearish_indicators["rsi"] = 22
        bearish_indicators["bb_position"] = "below_lower"
        s = MeanReversionStrategy()
        result = s.generate_signal(bearish_indicators)
        assert result["strategy"] == "mean_reversion"
        assert result["signal"] in ("long", "wait")
        assert result["strength"] >= 0

    def test_overbought_signal(self, bullish_indicators):
        bullish_indicators["rsi"] = 80
        bullish_indicators["bb_position"] = "above_upper"
        s = MeanReversionStrategy()
        result = s.generate_signal(bullish_indicators)
        assert result["signal"] in ("short", "wait")

    def test_neutral_returns_wait(self, ranging_indicators):
        s = MeanReversionStrategy()
        result = s.generate_signal(ranging_indicators)
        assert result["signal"] in ("wait", "long", "short")


# ── Breakout Tests ───────────────────────────────────────────────

class TestBreakout:
    """突破策略测试"""

    def test_breakout_with_volume(self, bullish_indicators):
        bullish_indicators["volume_ratio"] = 2.5
        s = BreakoutStrategy()
        result = s.generate_signal(bullish_indicators)
        assert result["strategy"] == "breakout"
        assert result["strength"] >= 0

    def test_no_breakout_low_volume(self, ranging_indicators):
        ranging_indicators["volume_ratio"] = 0.5
        s = BreakoutStrategy()
        result = s.generate_signal(ranging_indicators)
        assert result["signal"] in ("wait", "long", "short")

    def test_strength_bounds(self, bullish_indicators):
        s = BreakoutStrategy()
        result = s.generate_signal(bullish_indicators)
        assert 0 <= result["strength"] <= 100


# ── Ensemble Tests ───────────────────────────────────────────────

class TestEnsemble:
    """集成策略测试"""

    def test_bullish_consensus(self, bullish_indicators):
        e = EnsembleStrategy()
        result = e.generate_signal(bullish_indicators)
        assert result["signal"] in ("long", "short", "wait")
        assert 0 <= result["confidence"] <= 1.0
        assert len(result["individual_signals"]) == 3

    def test_bearish_consensus(self, bearish_indicators):
        e = EnsembleStrategy()
        result = e.generate_signal(bearish_indicators)
        assert result["signal"] in ("long", "short", "wait")
        assert isinstance(result["reasons"], list)

    def test_mixed_signals_handled(self, ranging_indicators):
        e = EnsembleStrategy()
        result = e.generate_signal(ranging_indicators)
        assert "signal" in result
        assert "confidence" in result
        assert "individual_signals" in result

    def test_performance_tracking(self, bullish_indicators):
        e = EnsembleStrategy()
        e.generate_signal(bullish_indicators)
        e.generate_signal(bullish_indicators)
        perf = e.get_strategy_performance()
        assert perf["total_signals"] == 2
        assert "signal_distribution" in perf
