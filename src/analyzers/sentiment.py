"""
新闻情绪分析引擎
分析新闻情绪、追踪7天趋势、单条新闻评分
使用 MiMo 模型进行 NLP 情绪判断
"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from src.utils.mimo_client import MiMoClient, MiMoMessage

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """新闻情绪分析引擎"""

    def __init__(self, mimo_client: MiMoClient):
        self.mimo = mimo_client
        self._history: list[dict] = []

    # ------------------------------------------------------------------
    # 新闻批量分析
    # ------------------------------------------------------------------

    async def analyze_news(
        self,
        news_items: list[dict],
        symbol: str,
    ) -> dict:
        """
        分析一批新闻的情绪

        Args:
            news_items: [{"title", "summary", "source", "time"}]
            symbol: 交易对

        Returns:
            {overall_score, classification, individual_scores, interpretation}
        """
        if not news_items:
            return {
                "overall_score": 0,
                "classification": "neutral",
                "individual_scores": [],
                "interpretation": "无可用新闻数据",
            }

        try:
            response = await self.mimo.analyze_news_sentiment(news_items, symbol)
            content = response.content or ""

            # 解析评分
            scores = self._extract_scores(content, len(news_items))

            overall = sum(scores) / len(scores) if scores else 0
            classification = self._score_to_classification(overall)

            result = {
                "overall_score": round(overall, 2),
                "classification": classification,
                "individual_scores": scores,
                "interpretation": content[:300],
                "news_count": len(news_items),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            self._history.append(result)
            return result

        except Exception as e:
            logger.error(f"News sentiment analysis failed: {e}")
            return {
                "overall_score": 0,
                "classification": "neutral",
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # 7天趋势
    # ------------------------------------------------------------------

    async def get_7day_trend(self, symbol: str) -> dict:
        """
        获取最近7天的情绪趋势

        Returns:
            {scores_by_day, trend_direction, trend_strength}
        """
        # 从历史记录中取最近7天
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent = [
            h for h in self._history
            if datetime.strptime(h.get("timestamp", "2000-01-01"), "%Y-%m-%d %H:%M:%S") >= seven_days_ago
        ]

        if len(recent) < 2:
            return {
                "scores_by_day": [],
                "trend_direction": "insufficient_data",
                "trend_strength": 0,
                "data_points": len(recent),
            }

        # 按天聚合
        daily_scores: dict[str, list[float]] = {}
        for h in recent:
            day = h.get("timestamp", "")[:10]
            score = h.get("overall_score", 0)
            daily_scores.setdefault(day, []).append(score)

        scores_by_day = []
        for day in sorted(daily_scores.keys()):
            avg = sum(daily_scores[day]) / len(daily_scores[day])
            scores_by_day.append({"date": day, "avg_score": round(avg, 2)})

        # 计算趋势方向
        if len(scores_by_day) >= 2:
            first_half = sum(s["avg_score"] for s in scores_by_day[: len(scores_by_day) // 2]) / (len(scores_by_day) // 2)
            second_half = sum(s["avg_score"] for s in scores_by_day[len(scores_by_day) // 2 :]) / (
                len(scores_by_day) - len(scores_by_day) // 2
            )
            diff = second_half - first_half
            if diff > 0.5:
                direction = "improving"
            elif diff < -0.5:
                direction = "deteriorating"
            else:
                direction = "stable"
            strength = round(abs(diff), 2)
        else:
            direction = "stable"
            strength = 0

        return {
            "scores_by_day": scores_by_day,
            "trend_direction": direction,
            "trend_strength": strength,
            "data_points": len(recent),
        }

    # ------------------------------------------------------------------
    # 单条新闻评分
    # ------------------------------------------------------------------

    async def score_single_news(self, title: str, summary: str = "", symbol: str = "") -> dict:
        """
        对单条新闻进行情绪评分

        Args:
            title: 新闻标题
            summary: 新闻摘要
            symbol: 关联交易对

        Returns:
            {score, classification, reason}
        """
        text = f"{title}。{summary}" if summary else title

        prompt = (
            f"请对以下{'关于' + symbol + '的' if symbol else ''}新闻进行情绪评分。\n"
            "评分范围：-5（极度恐慌）到 +5（极度贪婪）\n"
            "请直接给出：评分数字 | 原因（20字内）\n\n"
            f"新闻：{text}"
        )

        try:
            response = await self.mimo.quick_analysis(prompt)
            content = response.content or ""

            score = self._extract_single_score(content)
            classification = self._score_to_classification(score)

            return {
                "title": title[:80],
                "score": score,
                "classification": classification,
                "reason": content.strip()[:100],
            }
        except Exception as e:
            logger.error(f"Single news scoring failed: {e}")
            return {"title": title[:80], "score": 0, "classification": "neutral", "error": str(e)}

    # ------------------------------------------------------------------
    # 综合情绪报告
    # ------------------------------------------------------------------

    async def comprehensive_sentiment(
        self,
        fear_greed_value: int,
        news_items: list[dict],
        symbol: str,
    ) -> dict:
        """
        生成综合情绪报告（恐慌贪婪指数 + 新闻情绪）

        Args:
            fear_greed_value: 恐慌贪婪指数 (0-100)
            news_items: 新闻列表
            symbol: 交易对

        Returns:
            {composite_score, fear_greed, news_sentiment, trend_7d, overall}
        """
        news_result = await self.analyze_news(news_items, symbol)
        trend_7d = await self.get_7day_trend(symbol)

        # 归一化恐慌贪婪到 -5 ~ +5
        fg_normalized = (fear_greed_value - 50) / 10

        # 综合评分：恐慌贪婪 40% + 新闻情绪 60%
        composite = fg_normalized * 0.4 + news_result.get("overall_score", 0) * 0.6

        return {
            "composite_score": round(composite, 2),
            "fear_greed": {
                "value": fear_greed_value,
                "normalized": round(fg_normalized, 2),
            },
            "news_sentiment": {
                "score": news_result.get("overall_score", 0),
                "classification": news_result.get("classification", "neutral"),
                "news_count": news_result.get("news_count", 0),
            },
            "trend_7d": trend_7d,
            "overall": self._score_to_classification(composite),
        }

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_scores(content: str, count: int) -> list[float]:
        """从 MiMo 回复中提取评分列表"""
        import re

        # 匹配数字评分（-5 到 +5）
        pattern = r"[-+]?\d+\.?\d*"
        found = re.findall(pattern, content)

        scores = []
        for s in found:
            try:
                val = float(s)
                if -5 <= val <= 5:
                    scores.append(val)
            except ValueError:
                continue

        # 确保数量匹配
        while len(scores) < count:
            scores.append(0.0)

        return scores[:count]

    @staticmethod
    def _extract_single_score(content: str) -> float:
        """从回复中提取单个评分"""
        import re

        match = re.search(r"[-+]?\d+\.?\d*", content)
        if match:
            try:
                val = float(match.group())
                return max(-5, min(5, val))
            except ValueError:
                pass
        return 0.0

    @staticmethod
    def _score_to_classification(score: float) -> str:
        """将评分转为分类"""
        if score >= 3:
            return "extreme_greed"
        elif score >= 1.5:
            return "greed"
        elif score >= 0.5:
            return "slightly_greedy"
        elif score > -0.5:
            return "neutral"
        elif score > -1.5:
            return "slightly_fearful"
        elif score > -3:
            return "fear"
        else:
            return "extreme_fear"
