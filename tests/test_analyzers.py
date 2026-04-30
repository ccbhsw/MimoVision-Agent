"""
测试模块 - 技术分析器
"""
import pytest
import pandas as pd
import numpy as np

from src.analyzers.technical import TechnicalAnalyzer


class TestTechnicalAnalyzer:
    """技术指标计算测试"""

    @pytest.fixture
    def sample_klines(self):
        """生成模拟K线数据"""
        np.random.seed(42)
        n = 200
        base_price = 50000

        dates = pd.date_range(start="2024-01-01", periods=n, freq="h")
        prices = base_price + np.cumsum(np.random.randn(n) * 100)

        klines = []
        for i in range(n):
            price = prices[i]
            klines.append({
                "open_time": int(dates[i].timestamp() * 1000),
                "open": price - 50,
                "high": price + abs(np.random.randn() * 200),
                "low": price - abs(np.random.randn() * 200),
                "close": price,
                "volume": abs(np.random.randn() * 1000000),
            })

        return klines

    def test_klines_to_dataframe(self, sample_klines):
        """测试K线转DataFrame"""
        df = TechnicalAnalyzer.klines_to_dataframe(sample_klines)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 200
        assert "open" in df.columns
        assert "close" in df.columns

    def test_calculate_all(self, sample_klines):
        """测试全部技术指标计算"""
        df = TechnicalAnalyzer.klines_to_dataframe(sample_klines)
        result = TechnicalAnalyzer.calculate_all(df)

        # 验证所有预期指标都存在
        expected_keys = [
            "ema_9", "ema_21", "ema_50", "ema_200",
            "rsi", "rsi_signal",
            "macd", "macd_signal", "macd_histogram", "macd_cross",
            "bb_upper", "bb_middle", "bb_lower", "bb_position",
            "atr", "atr_pct",
            "kdj_k", "kdj_d", "kdj_j",
            "volume", "volume_ma", "volume_ratio",
            "support_levels", "resistance_levels",
            "trend", "current_price",
        ]

        for key in expected_keys:
            assert key in result, f"Missing indicator: {key}"

        # 验证值范围
        assert 0 <= result["rsi"] <= 100
        assert result["trend"] in ["bullish", "bearish", "ranging"]
        assert result["current_price"] > 0

    def test_format_analysis(self, sample_klines):
        """测试分析结果格式化"""
        df = TechnicalAnalyzer.klines_to_dataframe(sample_klines)
        indicators = TechnicalAnalyzer.calculate_all(df)
        text = TechnicalAnalyzer.format_analysis(indicators, "BTCUSDT", "1H")

        assert "BTCUSDT" in text
        assert "1H" in text
        assert "RSI" in text
        assert "MACD" in text
