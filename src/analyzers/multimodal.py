"""
MiMo 多模态分析模块
使用 MiMo 视觉模型分析K线图表、比较多周期形态、检测图表形态
"""
import logging
from typing import Optional
from pathlib import Path

from src.utils.mimo_client import MiMoClient, MiMoMessage, MiMoResponse

logger = logging.getLogger(__name__)


class MultimodalAnalyzer:
    """MiMo 多模态分析器"""

    def __init__(self, mimo_client: MiMoClient):
        self.mimo = mimo_client

    # ------------------------------------------------------------------
    # 单图分析
    # ------------------------------------------------------------------

    async def analyze_chart_image(
        self,
        image_path: str | bytes,
        symbol: str,
        timeframe: str,
        extra_prompt: Optional[str] = None,
    ) -> dict:
        """
        分析单张K线图表

        Args:
            image_path: 图片路径或字节
            symbol: 交易对
            timeframe: 时间周期
            extra_prompt: 额外提示

        Returns:
            {trend, support, resistance, signals, summary, raw_response}
        """
        try:
            response = await self.mimo.analyze_chart(
                image_path=image_path,
                symbol=symbol,
                timeframe=timeframe,
                prompt=extra_prompt,
            )
            return self._parse_analysis(response, symbol, timeframe)
        except Exception as e:
            logger.error(f"Chart analysis failed for {symbol} {timeframe}: {e}")
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "trend": "unknown",
                "error": str(e),
                "summary": f"分析失败: {e}",
            }

    # ------------------------------------------------------------------
    # 多周期对比
    # ------------------------------------------------------------------

    async def compare_timeframes(
        self,
        analyses: list[dict],
        symbol: str,
    ) -> dict:
        """
        对比多个时间周期的分析结果，寻找一致性

        Args:
            analyses: 多个 {symbol, timeframe, trend, ...} 字典
            symbol: 交易对

        Returns:
            {overall_direction, consistency, conflict_resolution, recommendation}
        """
        trends = [a.get("trend", "unknown") for a in analyses if a.get("trend")]

        if not trends:
            return {"overall_direction": "unknown", "consistency": 0}

        # 统计方向一致性
        bullish_count = sum(1 for t in trends if t in ("bullish", "long", "up"))
        bearish_count = sum(1 for t in trends if t in ("bearish", "short", "down"))
        ranging_count = sum(1 for t in trends if t in ("ranging", "neutral", "consolidation"))

        total = len(trends)
        if bullish_count > bearish_count and bullish_count > ranging_count:
            overall = "bullish"
            consistency = bullish_count / total
        elif bearish_count > bullish_count and bearish_count > ranging_count:
            overall = "bearish"
            consistency = bearish_count / total
        else:
            overall = "ranging"
            consistency = ranging_count / total

        # 用 MiMo 做冲突解决
        conflict_resolution = ""
        if consistency < 0.6:
            conflict_resolution = await self._resolve_conflict(analyses, symbol)

        # 权重：大周期优先
        tf_weights = {"1W": 3.0, "1D": 2.5, "4H": 2.0, "1H": 1.5, "15m": 1.0}
        weighted_score = 0
        total_weight = 0
        for a in analyses:
            tf = a.get("timeframe", "1H")
            w = tf_weights.get(tf, 1.0)
            if a.get("trend") in ("bullish", "long", "up"):
                weighted_score += w
            elif a.get("trend") in ("bearish", "short", "down"):
                weighted_score -= w
            total_weight += w

        direction_score = weighted_score / total_weight if total_weight else 0

        return {
            "overall_direction": overall,
            "direction_score": round(direction_score, 2),
            "consistency": round(consistency, 2),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "ranging_count": ranging_count,
            "conflict_resolution": conflict_resolution,
            "recommendation": self._make_recommendation(overall, consistency, direction_score),
        }

    # ------------------------------------------------------------------
    # 图表形态检测
    # ------------------------------------------------------------------

    async def detect_patterns(
        self,
        image_path: str | bytes,
        symbol: str,
        timeframe: str,
    ) -> dict:
        """
        检测K线图表中的常见形态

        Args:
            image_path: 图片路径或字节
            symbol: 交易对
            timeframe: 时间周期

        Returns:
            {patterns_found, reliability, implications}
        """
        prompt = (
            f"请分析 {symbol} {timeframe} K线图表中出现的经典图表形态。"
            "重点检查以下形态：\n"
            "1. 头肩顶/头肩底 (Head & Shoulders)\n"
            "2. 双顶/双底 (Double Top/Bottom)\n"
            "3. 三角形形态 (Triangle - Ascending/Descending/Symmetric)\n"
            "4. 旗形/三角旗 (Flag/Pennant)\n"
            "5. 楔形 (Wedge - Rising/Falling)\n"
            "6. 矩形整理 (Rectangle/Range)\n"
            "7. 杯柄形态 (Cup and Handle)\n"
            "8. 缺口 (Gaps)\n\n"
            "如果发现形态，请说明：\n"
            "- 形态名称\n"
            "- 当前处于形态的哪个阶段\n"
            "- 预期突破方向\n"
            "- 目标价位\n"
            "- 可靠性评估(1-5星)\n\n"
            "如果没有明显形态，请说明当前价格结构特征。"
        )

        try:
            response = await self.mimo.analyze_chart(
                image_path=image_path,
                symbol=symbol,
                timeframe=timeframe,
                prompt=prompt,
            )

            content = response.content.lower() if response.content else ""

            patterns = []
            pattern_keywords = {
                "头肩": "head_shoulders", "head and shoulders": "head_shoulders",
                "双顶": "double_top", "double top": "double_top",
                "双底": "double_bottom", "double bottom": "double_bottom",
                "三角": "triangle",
                "旗形": "flag", "pennant": "pennant",
                "楔形": "wedge", "wedge": "wedge",
                "矩形": "rectangle", "range": "rectangle",
                "杯柄": "cup_handle", "cup and handle": "cup_handle",
                "缺口": "gap", "gap": "gap",
            }

            for keyword, pattern_name in pattern_keywords.items():
                if keyword in content:
                    patterns.append(pattern_name)

            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "patterns_found": patterns,
                "pattern_count": len(patterns),
                "raw_analysis": response.content,
            }
        except Exception as e:
            logger.error(f"Pattern detection failed for {symbol} {timeframe}: {e}")
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "patterns_found": [],
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _parse_analysis(self, response: MiMoResponse, symbol: str, timeframe: str) -> dict:
        """解析 MiMo 响应为结构化结果"""
        content = response.content or ""

        trend = "unknown"
        content_lower = content.lower()
        # 简单关键词匹配判断趋势
        if any(w in content_lower for w in ["看多", "多头", "上涨", "bullish", "uptrend", "上升趋势"]):
            trend = "bullish"
        elif any(w in content_lower for w in ["看空", "空头", "下跌", "bearish", "downtrend", "下降趋势"]):
            trend = "bearish"
        elif any(w in content_lower for w in ["震荡", "盘整", "ranging", "sideways", "consolidation"]):
            trend = "ranging"

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trend": trend,
            "summary": content[:500],
            "reasoning": response.reasoning,
            "model": response.model,
            "raw_response": content,
        }

    async def _resolve_conflict(self, analyses: list[dict], symbol: str) -> str:
        """用 MiMo 解决多周期信号冲突"""
        summaries = []
        for a in analyses:
            summaries.append(
                f"- {a.get('timeframe', '?')}: {a.get('trend', '?')} | {a.get('summary', '')[:100]}"
            )

        prompt = (
            f"{symbol} 的不同时间周期分析结果存在冲突，请综合判断：\n"
            + "\n".join(summaries)
            + "\n\n请给出你的最终判断和理由（50字以内）。"
        )

        try:
            resp = await self.mimo.quick_analysis(prompt)
            return resp.content or ""
        except Exception:
            return ""

    @staticmethod
    def _make_recommendation(direction: str, consistency: float, score: float) -> str:
        """根据一致性生成建议"""
        if consistency >= 0.75:
            return f"多周期高度一致，{direction}方向可考虑入场"
        elif consistency >= 0.5:
            return f"多周期偏{direction}，建议等待更强确认信号"
        else:
            return "多周期信号冲突严重，建议观望"
