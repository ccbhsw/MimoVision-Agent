"""
K线图表生成模块
生成带有技术指标的专业K线图表，用于MiMo多模态分析
"""
import matplotlib
matplotlib.use('Agg')  # 无头模式
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import numpy as np
import io
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class ChartGenerator:
    """K线图表生成器"""

    # 自定义样式
    MC_STYLE = mpf.make_mpf_style(
        base_mpf_style='yahoo',
        marketcolors=mpf.make_marketcolors(
            up='#00C853',
            down='#FF1744',
            edge='inherit',
            wick='inherit',
            volume={'up': '#00C853', 'down': '#FF1744'},
        ),
        gridstyle='--',
        gridcolor='#e0e0e0',
        figcolor='#ffffff',
    )

    @staticmethod
    def generate_chart(
        klines: list[dict],
        symbol: str,
        timeframe: str,
        indicators: Optional[dict] = None,
        output_path: Optional[str] = None,
        width: int = 1920,
        height: int = 1080,
    ) -> bytes | str:
        """
        生成K线图表

        Args:
            klines: K线数据
            symbol: 交易对
            timeframe: 时间周期
            indicators: 技术指标数据（可选，会在图上叠加）
            output_path: 输出文件路径，None则返回字节数据
            width: 图片宽度
            height: 图片高度

        Returns:
            如果 output_path 为 None，返回 PNG 字节数据
            否则返回保存的文件路径
        """
        # 转换数据
        df = pd.DataFrame(klines)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df.index = pd.to_datetime(df['open_time'], unit='ms')

        # 计算附加指标用于图表叠加
        apds = []

        # EMA线
        for period, color in [(9, '#FF9800'), (21, '#2196F3'), (50, '#9C27B0')]:
            ema = df['close'].ewm(span=period, adjust=False).mean()
            apds.append(mpf.make_addplot(ema, color=color, width=1.2, label=f'EMA{period}'))

        # 布林带
        bb_sma = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        bb_upper = bb_sma + (bb_std * 2)
        bb_lower = bb_sma - (bb_std * 2)
        apds.append(mpf.make_addplot(bb_upper, color='#607D8B', width=0.8, linestyle='--', label='BB Upper'))
        apds.append(mpf.make_addplot(bb_lower, color='#607D8B', width=0.8, linestyle='--', label='BB Lower'))

        # RSI (子图)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        apds.append(mpf.make_addplot(rsi, panel=2, color='#7C4DFF', width=1.2, label='RSI(14)'))

        # MACD (子图)
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        # MACD颜色
        macd_colors = ['#00C853' if v >= 0 else '#FF1744' for v in histogram]
        apds.append(mpf.make_addplot(macd_line, panel=3, color='#2196F3', width=1.0, label='MACD'))
        apds.append(mpf.make_addplot(signal_line, panel=3, color='#FF9800', width=1.0, label='Signal'))
        apds.append(mpf.make_addplot(histogram, panel=3, type='bar', color=macd_colors, width=0.6))

        # 标题
        title = f"{symbol} | {timeframe}"
        if indicators:
            trend = indicators.get("trend", "")
            rsi_val = indicators.get("rsi", "")
            title += f" | Trend: {trend.upper()} | RSI: {rsi_val}"

        # DPI计算
        dpi = 100
        figsize = (width / dpi, height / dpi)

        # 生成图表
        kwargs = dict(
            type='candle',
            style=ChartGenerator.MC_STYLE,
            title=title,
            volume=True,
            addplot=apds,
            figsize=figsize,
            panel_sizes=[3, 1, 1, 1],  # 主图、成交量、RSI、MACD
            returnfig=True,
        )

        fig, axes = mpf.plot(df, **kwargs)

        # 添加RSI水平线
        if len(axes) > 2:
            axes[2].axhline(y=70, color='r', linestyle='--', linewidth=0.5, alpha=0.5)
            axes[2].axhline(y=30, color='g', linestyle='--', linewidth=0.5, alpha=0.5)

        # 保存或返回字节
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white')
            plt.close(fig)
            return output_path
        else:
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor='white')
            plt.close(fig)
            buf.seek(0)
            return buf.read()

    @staticmethod
    def generate_multi_timeframe_charts(
        klines_dict: dict[str, list[dict]],
        symbol: str,
        output_dir: str = "output/charts",
    ) -> dict[str, str]:
        """
        生成多周期图表

        Args:
            klines_dict: {"1H": [...], "4H": [...], "1D": [...]}
            symbol: 交易对

        Returns:
            {"1H": "path/to/1h_chart.png", ...}
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = {}
        for timeframe, klines in klines_dict.items():
            try:
                filename = f"{symbol}_{timeframe}.png"
                filepath = str(output_path / filename)
                ChartGenerator.generate_chart(
                    klines=klines,
                    symbol=symbol,
                    timeframe=timeframe,
                    output_path=filepath,
                )
                results[timeframe] = filepath
                logger.info(f"Generated chart: {filepath}")
            except Exception as e:
                logger.error(f"Failed to generate {symbol} {timeframe} chart: {e}")

        return results
