"""
新闻情绪分析Agent
利用MiMo模型分析新闻情绪和市场情绪
"""
import asyncio
import logging
import re
from typing import Optional
from datetime import datetime

from src.utils.mimo_client import MiMoClient, MiMoMessage
from src.data_collectors.news_collector import NewsCollector

logger = logging.getLogger(__name__)


class NewsAgent:
    """新闻情绪分析Agent - 采集多源新闻并量化市场情绪"""

    def __init__(
        self,
        mimo_client: MiMoClient,
        news_collector: Optional[NewsCollector] = None,
        brave_api_key: str = "",
        proxy: str = "",
    ):
        self.mimo = mimo_client
        self.news = news_collector or NewsCollector(
            brave_api_key=brave_api_key, proxy=proxy,
        )

    async def analyze_sentiment(self, news_items: list[dict], symbol: str) -> dict:
        """
        分析新闻情绪，返回整体评分和逐条评分

        Returns:
            {overall_score, classification, individual_scores, mimo_analysis, recommendation, confidence}
        """
        if not news_items:
            return {
                "overall_score": 0.0, "classification": "neutral",
                "individual_scores": [], "recommendation": "无新闻数据", "confidence": 0.0,
            }

        logger.info(f"NewsAgent: analyzing {len(news_items)} news for {symbol}")

        response = await self.mimo.analyze_news_sentiment(news_items=news_items, symbol=symbol)

        individual_scores = []
        for item in news_items:
            title = item.get("title", "")
            score = self._extract_score(response.content, title)
            individual_scores.append({
                "title": title,
                "source": item.get("source", ""),
                "time": item.get("time", ""),
                "score": score,
            })

        overall = sum(s["score"] for s in individual_scores) / len(individual_scores) if individual_scores else 0.0
        classification = self._classify(overall)

        rec_map = {
            "extreme_fear": "市场极度恐慌，可能超跌反弹机会",
            "fear": "情绪偏空，建议等待确认信号",
            "neutral": "情绪中性，结合技术面寻找方向",
            "greed": "偏贪婪，注意追高风险",
            "extreme_greed": "极度贪婪，警惕回调风险",
        }

        return {
            "overall_score": round(overall, 2),
            "classification": classification,
            "individual_scores": individual_scores,
            "mimo_analysis": response.content,
            "recommendation": rec_map.get(classification, ""),
            "confidence": min(len(news_items) / 5.0, 1.0),
        }

    async def get_comprehensive_news(self, symbol: str) -> dict:
        """获取综合新闻数据（多源并行采集）"""
        logger.info(f"NewsAgent: comprehensive news for {symbol}")

        brave_news, rss_news, fear_greed, global_data = await asyncio.gather(
            self.news.get_symbol_news(symbol, count=5),
            self.news.get_crypto_news_rss(count=10),
            self.news.get_fear_greed_index(),
            self.news.get_coingecko_global(),
            return_exceptions=True,
        )

        return {
            "brave_news": brave_news if isinstance(brave_news, list) else [],
            "rss_news": rss_news if isinstance(rss_news, list) else [],
            "fear_greed": fear_greed if isinstance(fear_greed, dict) else {},
            "coingecko_global": global_data if isinstance(global_data, dict) else {},
            "symbol": symbol,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def score_news_impact(self, news_items: list[dict], symbol: str) -> list[dict]:
        """
        评估每条新闻对市场的影响

        Returns:
            [{title, impact_score(1-10), direction(利多/利空/中性), timeframe, reason}]
        """
        if not news_items:
            return []

        news_text = "\n".join([
            f"{i+1}. [{n.get('source', '')}] {n.get('title', '')} - {n.get('snippet', n.get('summary', ''))}"
            for i, n in enumerate(news_items)
        ])

        prompt = (
            f"评估以下新闻对 {symbol} 合约的影响：\n{news_text}\n\n"
            "对每条新闻给出：影响评分(1-10)、方向(利多/利空/中性)、影响时间(短期/中期/长期)、原因"
        )

        messages = [
            MiMoMessage(role="system", content="你是加密货币新闻影响分析专家。"),
            MiMoMessage(role="user", content=prompt),
        ]

        response = await self.mimo.chat(
            messages=messages, model="mimo-v2-flash", temperature=0.2, max_tokens=2048,
        )

        results = []
        for item in news_items:
            title = item.get("title", "")
            direction = "中性"
            if "利多" in response.content or "看涨" in response.content:
                direction = "利多"
            elif "利空" in response.content or "看跌" in response.content:
                direction = "利空"

            results.append({
                "title": title,
                "source": item.get("source", ""),
                "impact_score": self._extract_score(response.content, title, scale=10),
                "direction": direction,
                "timeframe": "短期",
                "reason": "",
            })

        return results

    def _extract_score(self, text: str, context: str, scale: int = 5) -> float:
        """从文本中提取评分"""
        idx = text.find(context[:20]) if len(context) > 20 else text.find(context)
        if idx >= 0:
            nearby = text[idx:idx + 200]
            match = re.search(r'[-+]?\d+\.?\d*', nearby)
            if match:
                return max(-scale, min(scale, float(match.group())))
        return 0.0

    def _classify(self, score: float) -> str:
        """根据评分分类情绪"""
        if score <= -3:
            return "extreme_fear"
        elif score <= -1.5:
            return "fear"
        elif score < 1.5:
            return "neutral"
        elif score < 3:
            return "greed"
        return "extreme_greed"
