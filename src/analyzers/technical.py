"""
技术指标计算模块
基于 pandas-ta 计算各类技术指标
"""
import pandas as pd
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """技术指标分析器"""

    @staticmethod
    def klines_to_dataframe(klines: list[dict]) -> pd.DataFrame:
        """将K线数据转为DataFrame"""
        df = pd.DataFrame(klines)
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df.index = pd.to_datetime(df["open_time"], unit="ms")
        return df

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> dict:
        """计算所有技术指标"""
        result = {}

        # EMA (指数移动平均线)
        for period in [9, 21, 50, 200]:
            ema = df["close"].ewm(span=period, adjust=False).mean()
            result[f"ema_{period}"] = round(ema.iloc[-1], 4)
            result[f"ema_{period}_signal"] = "above" if df["close"].iloc[-1] > ema.iloc[-1] else "below"

        # RSI (相对强弱指数)
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        result["rsi"] = round(rsi.iloc[-1], 2)
        result["rsi_signal"] = (
            "overbought" if result["rsi"] > 70
            else "oversold" if result["rsi"] < 30
            else "neutral"
        )

        # MACD
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        result["macd"] = round(macd_line.iloc[-1], 4)
        result["macd_signal"] = round(signal_line.iloc[-1], 4)
        result["macd_histogram"] = round(histogram.iloc[-1], 4)
        result["macd_cross"] = (
            "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1]
            and macd_line.iloc[-2] <= signal_line.iloc[-2]
            else "bearish" if macd_line.iloc[-1] < signal_line.iloc[-1]
            and macd_line.iloc[-2] >= signal_line.iloc[-2]
            else "none"
        )

        # Bollinger Bands (布林带)
        bb_sma = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        bb_upper = bb_sma + (bb_std * 2)
        bb_lower = bb_sma - (bb_std * 2)
        result["bb_upper"] = round(bb_upper.iloc[-1], 4)
        result["bb_middle"] = round(bb_sma.iloc[-1], 4)
        result["bb_lower"] = round(bb_lower.iloc[-1], 4)
        result["bb_position"] = (
            "above_upper" if df["close"].iloc[-1] > bb_upper.iloc[-1]
            else "below_lower" if df["close"].iloc[-1] < bb_lower.iloc[-1]
            else "middle"
        )

        # ATR (平均真实波幅)
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=14).mean()
        result["atr"] = round(atr.iloc[-1], 4)
        result["atr_pct"] = round((atr.iloc[-1] / df["close"].iloc[-1]) * 100, 2)

        # KDJ (随机指标)
        low_9 = df["low"].rolling(window=9).min()
        high_9 = df["high"].rolling(window=9).max()
        rsv = (df["close"] - low_9) / (high_9 - low_9) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        result["kdj_k"] = round(k.iloc[-1], 2)
        result["kdj_d"] = round(d.iloc[-1], 2)
        result["kdj_j"] = round(j.iloc[-1], 2)

        # Volume analysis (成交量分析)
        vol_ma = df["volume"].rolling(window=20).mean()
        result["volume"] = round(df["volume"].iloc[-1], 2)
        result["volume_ma"] = round(vol_ma.iloc[-1], 2)
        result["volume_ratio"] = round(df["volume"].iloc[-1] / vol_ma.iloc[-1], 2)

        # Support/Resistance levels (支撑阻力位)
        recent = df.tail(50)
        result["support_levels"] = [
            round(recent["low"].nsmallest(3).iloc[i], 4) for i in range(min(3, len(recent)))
        ]
        result["resistance_levels"] = [
            round(recent["high"].nlargest(3).iloc[i], 4) for i in range(min(3, len(recent)))
        ]

        # Trend detection (趋势判断)
        ema9 = df["close"].ewm(span=9, adjust=False).mean()
        ema21 = df["close"].ewm(span=21, adjust=False).mean()
        ema50 = df["close"].ewm(span=50, adjust=False).mean()

        if ema9.iloc[-1] > ema21.iloc[-1] > ema50.iloc[-1]:
            result["trend"] = "bullish"
        elif ema9.iloc[-1] < ema21.iloc[-1] < ema50.iloc[-1]:
            result["trend"] = "bearish"
        else:
            result["trend"] = "ranging"

        result["current_price"] = round(df["close"].iloc[-1], 4)

        return result

    @staticmethod
    def format_analysis(indicators: dict, symbol: str, timeframe: str) -> str:
        """格式化技术分析结果为可读文本"""
        trend_emoji = {"bullish": "📈", "bearish": "📉", "ranging": "↔️"}
        trend = indicators.get("trend", "unknown")
        emoji = trend_emoji.get(trend, "❓")

        text = f"""## {symbol} {timeframe} 技术指标分析

### 趋势判断: {emoji} {trend.upper()}
- 当前价格: {indicators.get('current_price', 'N/A')}

### 移动平均线
- EMA9: {indicators.get('ema_9', 'N/A')} (价格在{indicators.get('ema_9_signal', 'N/A')})
- EMA21: {indicators.get('ema_21', 'N/A')} (价格在{indicators.get('ema_21_signal', 'N/A')})
- EMA50: {indicators.get('ema_50', 'N/A')} (价格在{indicators.get('ema_50_signal', 'N/A')})
- EMA200: {indicators.get('ema_200', 'N/A')} (价格在{indicators.get('ema_200_signal', 'N/A')})

### RSI: {indicators.get('rsi', 'N/A')} ({indicators.get('rsi_signal', 'N/A')})

### MACD
- MACD线: {indicators.get('macd', 'N/A')}
- 信号线: {indicators.get('macd_signal', 'N/A')}
- 柱状图: {indicators.get('macd_histogram', 'N/A')}
- 交叉信号: {indicators.get('macd_cross', 'N/A')}

### 布林带
- 上轨: {indicators.get('bb_upper', 'N/A')}
- 中轨: {indicators.get('bb_middle', 'N/A')}
- 下轨: {indicators.get('bb_lower', 'N/A')}
- 位置: {indicators.get('bb_position', 'N/A')}

### KDJ
- K: {indicators.get('kdj_k', 'N/A')}
- D: {indicators.get('kdj_d', 'N/A')}
- J: {indicators.get('kdj_j', 'N/A')}

### ATR: {indicators.get('atr', 'N/A')} ({indicators.get('atr_pct', 'N/A')}%)

### 成交量
- 当前: {indicators.get('volume', 'N/A')}
- MA20: {indicators.get('volume_ma', 'N/A')}
- 比率: {indicators.get('volume_ratio', 'N/A')}x

### 关键价位
- 支撑位: {indicators.get('support_levels', [])}
- 阻力位: {indicators.get('resistance_levels', [])}
"""
        return text
