"""
策略分析Agent
利用MiMo-V2.5-Pro进行深度策略推理
"""
import logging
import re
from typing import Optional

from src.utils.mimo_client import MiMoClient, MiMoMessage

logger = logging.getLogger(__name__)


class StrategyAgent:
    """
    策略分析Agent

    负责：
    - 综合多维度数据生成交易策略
    - 多周期共识判断
    - 简单信号回测验证
    """

    TIMEFRAME_WEIGHTS = {"15m": 0.10, "1H": 0.25, "4H": 0.30, "1D": 0.25, "1W": 0.10}

    def __init__(self, mimo_client: MiMoClient):
        self.mimo = mimo_client

    async def generate_strategy(
        self,
        market_data: dict,
        technical_analysis: str,
        chart_analysis: str,
        news_sentiment: str,
    ) -> dict:
        """
        综合推理生成交易策略

        Returns:
            {direction, entry_zone, stop_loss, take_profit, leverage, position_pct,
             risk_level, confidence, summary, key_levels}
        """
        logger.info("StrategyAgent: generating strategy with MiMo-V2.5-Pro")

        system_prompt = (
            "你是专业合约交易策略分析师。基于以下信息给出完整交易策略：\n"
            "1. 市场数据（价格、资金费率、持仓量、多空比）\n"
            "2. 技术指标多周期分析\n"
            "3. K线图表视觉分析\n"
            "4. 新闻面和市场情绪\n\n"
            "必须给出：方向(long/short/wait)、入场区间、止损、止盈(至少2个)、"
            "建议杠杆、仓位比例、风险等级(low/medium/high)、置信度(0-100)"
        )

        user_content = (
            f"## 市场数据\n"
            f"价格: {market_data.get('price', 'N/A')} | "
            f"24h涨跌: {market_data.get('change_24h', 'N/A')}% | "
            f"资金费率: {market_data.get('funding_rate', 'N/A')} | "
            f"持仓量: {market_data.get('open_interest', 'N/A')} | "
            f"多空比: {market_data.get('long_short_ratio', 'N/A')}\n\n"
            f"## 技术指标\n{technical_analysis}\n\n"
            f"## 图表分析\n{chart_analysis}\n\n"
            f"## 新闻情绪\n{news_sentiment}"
        )

        messages = [
            MiMoMessage(role="system", content=system_prompt),
            MiMoMessage(role="user", content=user_content),
        ]

        response = await self.mimo.chat(
            messages=messages, model="mimo-v2.5-pro", temperature=0.4, max_tokens=4096,
        )

        content = response.content

        direction = "wait"
        cl = content.lower()
        if "做多" in content or "long" in cl or "买入" in content:
            direction = "long"
        elif "做空" in content or "short" in cl or "卖出" in content:
            direction = "short"

        leverage = 20
        for word in content.split():
            if "x" in word.lower() and any(c.isdigit() for c in word):
                try:
                    leverage = int(''.join(c for c in word if c.isdigit()))
                except ValueError:
                    pass

        confidence = 50
        conf_match = re.search(r'置信度[:\s]*(\d+)', content)
        if conf_match:
            confidence = int(conf_match.group(1))

        risk_level = "medium"
        if "高风险" in content or "high" in cl:
            risk_level = "high"
        elif "低风险" in content or "low" in cl:
            risk_level = "low"

        return {
            "direction": direction,
            "entry_zone": self._extract_price_range(content, "入场"),
            "stop_loss": self._extract_price(content, "止损"),
            "take_profit": self._extract_price(content, "止盈"),
            "leverage": leverage,
            "position_pct": 10.0,
            "risk_level": risk_level,
            "confidence": confidence,
            "summary": content,
            "key_levels": self._extract_key_levels(content, market_data),
        }

    async def generate_multi_timeframe_consensus(self, timeframe_analyses: dict) -> dict:
        """多周期共识判断（加权投票）"""
        votes = {"long": 0.0, "short": 0.0, "wait": 0.0}

        for tf, analysis in timeframe_analyses.items():
            weight = self.TIMEFRAME_WEIGHTS.get(tf, 0.15)
            direction = analysis.get("direction", "wait")
            strength = analysis.get("strength", 50) / 100.0
            votes[direction] += weight * strength

        total = sum(votes.values()) or 1.0
        consensus_dir = max(votes, key=votes.get)
        consensus_strength = votes[consensus_dir] / total

        agreement_pct = round(consensus_strength * 100, 1)

        dominant_tf = max(
            timeframe_analyses.keys(),
            key=lambda tf: self.TIMEFRAME_WEIGHTS.get(tf, 0.15) * (
                timeframe_analyses[tf].get("strength", 50) / 100.0
            ),
        )

        return {
            "direction": consensus_dir,
            "consensus_strength": round(consensus_strength, 3),
            "agreement_pct": agreement_pct,
            "dominant_timeframe": dominant_tf,
            "vote_distribution": {k: round(v / total, 3) for k, v in votes.items()},
        }

    async def backtest_signal(self, indicators: list[dict], direction: str, window: int = 20) -> dict:
        """简单回测信号验证"""
        if len(indicators) < window:
            return {"win_rate": 0.5, "avg_pnl_pct": 0.0, "total_trades": 0, "sharpe_estimate": 0.0}

        recent = indicators[-window:]
        wins, pnls = 0, []

        for i in range(1, len(recent)):
            prev, curr = recent[i - 1], recent[i]
            prev_price = prev.get("current_price", 0)
            curr_price = curr.get("current_price", 0)
            if prev_price == 0:
                continue

            prev_trend = prev.get("trend", "ranging")
            pnl_pct = (curr_price - prev_price) / prev_price * 100

            if direction == "long" and prev_trend in ("bullish", "ranging"):
                if pnl_pct > 0:
                    wins += 1
                pnls.append(pnl_pct)
            elif direction == "short" and prev_trend in ("bearish", "ranging"):
                if pnl_pct < 0:
                    wins += 1
                pnls.append(abs(pnl_pct))

        import numpy as np
        total_trades = len(pnls)
        win_rate = wins / total_trades if total_trades > 0 else 0.5
        avg_pnl = sum(pnls) / total_trades if total_trades > 0 else 0.0
        sharpe = float(np.mean(pnls) / (np.std(pnls) + 1e-8)) if len(pnls) > 2 else 0.0

        return {
            "win_rate": round(win_rate, 3),
            "avg_pnl_pct": round(avg_pnl, 4),
            "total_trades": total_trades,
            "sharpe_estimate": round(sharpe, 2),
        }

    def _extract_price_range(self, text: str, keyword: str) -> str:
        match = re.search(rf'{keyword}[^。\n]*?(\d+[,.]?\d*)\s*[-~至到]\s*(\d+[,.]?\d*)', text)
        return f"{match.group(1)} - {match.group(2)}" if match else "N/A"

    def _extract_price(self, text: str, keyword: str) -> str:
        match = re.search(rf'{keyword}[^。\n]*?(\d+[,.]?\d*)', text)
        return match.group(1) if match else "N/A"

    def _extract_key_levels(self, text: str, market_data: dict) -> dict:
        prices = [float(p.replace(",", "")) for p in re.findall(r'\$(\d+[,.]?\d*)', text)]
        current = market_data.get("price", 0)
        return {
            "supports": sorted([p for p in prices if p < current], reverse=True)[:3],
            "resistances": sorted([p for p in prices if p > current])[:3],
        }
