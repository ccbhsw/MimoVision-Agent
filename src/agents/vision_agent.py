"""
多模态视觉分析Agent
利用MiMo-V2-Omni的视觉能力分析K线图表
"""
import asyncio
import logging
from typing import Optional

from src.utils.mimo_client import MiMoClient
from src.analyzers.chart_generator import ChartGenerator

logger = logging.getLogger(__name__)


class VisionAgent:
    """
    多模态视觉分析Agent

    负责：
    - 生成专业K线图表
    - 调用MiMo-Omni进行图表视觉分析
    - 支持多周期批量分析
    - 支持自定义prompt分析
    """

    def __init__(self, mimo_client: MiMoClient):
        self.mimo = mimo_client

    async def analyze_chart(
        self,
        klines: list[dict],
        symbol: str,
        timeframe: str,
        indicators: Optional[dict] = None,
    ) -> str:
        """
        生成图表并进行MiMo视觉分析

        Args:
            klines: K线数据
            symbol: 交易对
            timeframe: 时间周期
            indicators: 技术指标数据

        Returns:
            视觉分析文本
        """
        logger.info(f"VisionAgent: analyzing {symbol} {timeframe}")

        # 生成图表
        chart_bytes = ChartGenerator.generate_chart(
            klines=klines,
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators,
        )

        # 构建带指标的prompt
        prompt = f"请分析 {symbol} {timeframe} 周期的K线图表。"
        if indicators:
            trend = indicators.get("trend", "unknown")
            rsi = indicators.get("rsi", "N/A")
            prompt += f"\n当前趋势判断为{trend}，RSI为{rsi}。请结合图表验证并补充分析。"

        # 调用MiMo多模态分析
        response = await self.mimo.analyze_chart(
            image_path=chart_bytes,
            symbol=symbol,
            timeframe=timeframe,
            prompt=prompt,
        )

        return response.content

    async def analyze_multiple_timeframes(
        self,
        klines_dict: dict[str, list[dict]],
        symbol: str,
        indicators_dict: Optional[dict[str, dict]] = None,
    ) -> dict[str, str]:
        """
        批量多周期分析

        Args:
            klines_dict: {"1H": [...], "4H": [...], ...}
            symbol: 交易对
            indicators_dict: {"1H": {...}, "4H": {...}, ...}

        Returns:
            {"1H": "analysis_text", ...}
        """
        indicators_dict = indicators_dict or {}

        tasks = {}
        for timeframe, klines in klines_dict.items():
            if klines:
                tasks[timeframe] = asyncio.create_task(
                    self.analyze_chart(
                        klines=klines,
                        symbol=symbol,
                        timeframe=timeframe,
                        indicators=indicators_dict.get(timeframe),
                    )
                )

        results = {}
        for timeframe, task in tasks.items():
            try:
                results[timeframe] = await task
            except Exception as e:
                logger.error(f"Vision analysis failed for {symbol} {timeframe}: {e}")
                results[timeframe] = f"分析失败: {e}"

        return results

    async def analyze_with_custom_prompt(
        self,
        image_bytes: bytes,
        prompt: str,
        model: str = "mimo-v2-omni",
    ) -> str:
        """
        使用自定义prompt分析图片

        Args:
            image_bytes: 图片字节数据
            prompt: 自定义分析提示
            model: 使用的模型

        Returns:
            分析文本
        """
        from src.utils.mimo_client import MiMoMessage

        messages = [
            MiMoMessage(
                role="system",
                content="你是一个专业的金融图表分析师，擅长技术分析和形态识别。"
            ),
            MiMoMessage(
                role="user",
                content=self.mimo._build_image_content(prompt, image_bytes),
            ),
        ]

        response = await self.mimo.chat(
            messages=messages,
            model=model,
            temperature=0.3,
            max_tokens=2048,
        )

        return response.content

    async def detect_patterns(self, image_bytes: bytes) -> list[str]:
        """
        图表形态识别

        Args:
            image_bytes: K线图表图片

        Returns:
            识别到的形态列表，如 ["头肩顶", "双底", "上升三角形"]
        """
        prompt = (
            "请仔细观察这张K线图表，识别出其中包含的技术形态。"
            "包括但不限于：头肩顶/底、双顶/底、三角形、旗形、楔形、"
            "矩形整理、圆弧顶/底等。\n\n"
            "请以JSON数组格式返回识别到的形态名称，例如：\n"
            '["上升三角形", "双底"]\n\n'
            "如果没有明显形态，返回空数组 []"
        )

        result = await self.analyze_with_custom_prompt(image_bytes, prompt)

        # 尝试解析JSON
        import json
        try:
            # 提取JSON数组部分
            start = result.find('[')
            end = result.rfind(']') + 1
            if start >= 0 and end > start:
                patterns = json.loads(result[start:end])
                return patterns if isinstance(patterns, list) else []
        except (json.JSONDecodeError, ValueError):
            pass

        return []

    async def compare_timeframes(
        self,
        analyses: dict[str, str],
        symbol: str,
    ) -> str:
        """
        多周期对比分析

        Args:
            analyses: {"1H": "analysis1", "4H": "analysis2", ...}
            symbol: 交易对

        Returns:
            多周期对比结论
        """
        combined = "\n\n".join([
            f"### {tf} 周期分析\n{analysis}"
            for tf, analysis in analyses.items()
        ])

        prompt = (
            f"以下是 {symbol} 多个时间周期的技术分析结果：\n\n"
            f"{combined}\n\n"
            "请综合以上多周期分析，给出：\n"
            "1. 多周期是否共振？方向是否一致？\n"
            "2. 短期、中期、长期趋势分别是什么？\n"
            "3. 哪个周期的信号最可靠？\n"
            "4. 综合判断和操作建议"
        )

        from src.utils.mimo_client import MiMoMessage
        messages = [
            MiMoMessage(role="system", content="你是多周期技术分析专家。"),
            MiMoMessage(role="user", content=prompt),
        ]

        response = await self.mimo.chat(
            messages=messages,
            model="mimo-v2.5-pro",
            temperature=0.3,
            max_tokens=2048,
        )

        return response.content
