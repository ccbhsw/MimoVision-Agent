"""
Chain-of-Thought 推理引擎
利用 MiMo-V2.5-Pro 进行多步骤深度推理
"""
import asyncio
import logging
import re
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.utils.mimo_client import MiMoClient, MiMoMessage

logger = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    """单步推理结果"""
    step_id: int
    name: str
    hypothesis: str
    evidence: str
    conclusion: str
    confidence: float  # 0.0-1.0
    reasoning_text: str = ""
    contradictions: list[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class ReasoningChain:
    """完整推理链"""
    symbol: str
    steps: list[ReasoningStep] = field(default_factory=list)
    final_conclusion: str = ""
    overall_confidence: float = 0.0
    contradictions_found: list[str] = field(default_factory=list)
    model_used: str = ""
    total_tokens: int = 0
    timestamp: str = ""

    def add_step(self, step: ReasoningStep):
        self.steps.append(step)

    def get_step(self, name: str) -> Optional[ReasoningStep]:
        for s in self.steps:
            if s.name == name:
                return s
        return None

    def calculate_overall_confidence(self) -> float:
        if not self.steps:
            return 0.0
        weights = {
            "trend_analysis": 0.25,
            "indicator_consensus": 0.25,
            "multi_timeframe": 0.20,
            "news_sentiment": 0.15,
            "risk_assessment": 0.15,
        }
        weighted_sum = 0.0
        weight_total = 0.0
        for step in self.steps:
            w = weights.get(step.name, 0.1)
            weighted_sum += step.confidence * w
            weight_total += w
        self.overall_confidence = weighted_sum / weight_total if weight_total > 0 else 0.0
        return self.overall_confidence

    def format_chain(self) -> str:
        lines = [f"# {self.symbol} 推理链 ({self.timestamp})"]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"\n## Step {i}: {step.name}")
            lines.append(f"- **假设**: {step.hypothesis}")
            lines.append(f"- **证据**: {step.evidence[:300]}...")
            lines.append(f"- **结论**: {step.conclusion}")
            lines.append(f"- **置信度**: {step.confidence:.1%}")
            if step.contradictions:
                lines.append(f"- **矛盾**: {'; '.join(step.contradictions)}")
        lines.append(f"\n## 最终结论")
        lines.append(f"- **结论**: {self.final_conclusion}")
        lines.append(f"- **综合置信度**: {self.overall_confidence:.1%}")
        lines.append(f"- **发现矛盾**: {len(self.contradictions_found)}个")
        return "\n".join(lines)


class CoTEngine:
    """
    Chain-of-Thought 推理引擎

    执行多步骤推理：
    1. 趋势分析假设 → 验证
    2. 指标共识检查 → 矛盾检测
    3. 多周期交叉验证 → 共识度
    4. 新闻情绪融合 → 情绪偏差检测
    5. 风险综合评估 → 最终结论
    """

    REASONING_SYSTEM_PROMPT = (
        "你是一个专业的金融推理分析师，使用Chain-of-Thought进行深度推理。\n"
        "对于每个分析步骤，你必须：\n"
        "1. 先提出假设（Hypothesis）\n"
        "2. 列出支持/反对的证据（Evidence）\n"
        "3. 给出结论（Conclusion）\n"
        "4. 评估置信度（Confidence: 0-100%）\n"
        "5. 标记任何发现的矛盾（Contradictions）\n\n"
        "严格格式：\n"
        "HYPOTHESIS: ...\n"
        "EVIDENCE_SUPPORT: ...\n"
        "EVIDENCE_AGAINST: ...\n"
        "CONCLUSION: ...\n"
        "CONFIDENCE: XX%\n"
        "CONTRADICTIONS: ... (无则写None)"
    )

    def __init__(self, mimo_client: MiMoClient):
        self.mimo = mimo_client

    async def reason_full_analysis(
        self,
        symbol: str,
        market_data: dict,
        technical_indicators: dict[str, dict],
        chart_analyses: dict[str, str],
        news_sentiment: dict,
    ) -> ReasoningChain:
        """
        执行完整的Chain-of-Thought推理流程

        Returns:
            完整的推理链，包含5个步骤
        """
        chain = ReasoningChain(
            symbol=symbol,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            model_used="mimo-v2.5-pro",
        )

        # Step 1: 趋势分析推理
        step1 = await self._reason_trend(symbol, technical_indicators, market_data)
        chain.add_step(step1)

        # Step 2: 指标共识检查
        step2 = await self._reason_indicator_consensus(
            symbol, technical_indicators, step1
        )
        chain.add_step(step2)

        # Step 3: 多周期交叉验证
        step3 = await self._reason_multi_timeframe(
            symbol, technical_indicators, chart_analyses
        )
        chain.add_step(step3)

        # Step 4: 新闻情绪融合
        step4 = await self._reason_news_sentiment(
            symbol, news_sentiment, step1
        )
        chain.add_step(step4)

        # Step 5: 风险综合评估 + 最终结论
        step5 = await self._reason_final(
            symbol, chain.steps, market_data
        )
        chain.add_step(step5)

        # 汇总矛盾
        for step in chain.steps:
            chain.contradictions_found.extend(step.contradictions)

        # 计算综合置信度
        chain.calculate_overall_confidence()
        chain.final_conclusion = step5.conclusion

        return chain

    async def _run_reasoning_step(
        self,
        step_name: str,
        prompt: str,
        context: str,
    ) -> ReasoningStep:
        """执行单步推理"""
        messages = [
            MiMoMessage(role="system", content=self.REASONING_SYSTEM_PROMPT),
            MiMoMessage(role="user", content=f"## 分析任务: {step_name}\n\n{context}\n\n{prompt}"),
        ]

        response = await self.mimo.chat(
            messages=messages,
            model="mimo-v2.5-pro",
            temperature=0.3,
            max_tokens=3000,
        )

        text = response.content

        hypothesis = self._extract_section(text, "HYPOTHESIS")
        evidence = (
            self._extract_section(text, "EVIDENCE_SUPPORT")
            + "\n"
            + self._extract_section(text, "EVIDENCE_AGAINST")
        )
        conclusion = self._extract_section(text, "CONCLUSION")
        confidence = self._extract_confidence(text)
        contradictions = self._extract_contradictions(text)

        return ReasoningStep(
            step_id=0,
            name=step_name,
            hypothesis=hypothesis,
            evidence=evidence,
            conclusion=conclusion,
            confidence=confidence,
            reasoning_text=text,
            contradictions=contradictions,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def _reason_trend(
        self, symbol: str, indicators: dict, market_data: dict
    ) -> ReasoningStep:
        """Step 1: 趋势分析推理"""
        # 汇总各周期趋势
        trends = {}
        for tf, ind in indicators.items():
            trends[tf] = ind.get("trend", "unknown")

        context = (
            f"品种: {symbol}\n"
            f"当前价格: {market_data.get('price', 'N/A')}\n"
            f"24h涨跌: {market_data.get('change_24h', 'N/A')}%\n"
            f"各周期趋势: {trends}\n"
            f"资金费率: {market_data.get('funding_rate', 'N/A')}\n"
            f"持仓量变化: {market_data.get('open_interest', 'N/A')}\n"
            f"多空比: {market_data.get('long_short_ratio', 'N/A')}"
        )

        prompt = (
            "请基于以上数据推理当前趋势：\n"
            "1. 多周期趋势是否一致？\n"
            "2. 资金费率和持仓量支持哪个方向？\n"
            "3. 多空比反映的市场情绪是什么？\n"
            "4. 综合判断当前趋势方向和强度"
        )

        step = await self._run_reasoning_step("trend_analysis", prompt, context)
        step.step_id = 1
        return step

    async def _reason_indicator_consensus(
        self, symbol: str, indicators: dict, prev_step: ReasoningStep
    ) -> ReasoningStep:
        """Step 2: 指标共识检查"""
        ind_summary = {}
        for tf, ind in indicators.items():
            ind_summary[tf] = {
                "rsi": ind.get("rsi"),
                "rsi_signal": ind.get("rsi_signal"),
                "macd_cross": ind.get("macd_cross"),
                "bb_position": ind.get("bb_position"),
                "trend": ind.get("trend"),
                "volume_ratio": ind.get("volume_ratio"),
                "kdj_k": ind.get("kdj_k"),
                "kdj_d": ind.get("kdj_d"),
                "kdj_j": ind.get("kdj_j"),
            }

        context = (
            f"品种: {symbol}\n"
            f"上一步趋势判断: {prev_step.conclusion}\n"
            f"各周期技术指标:\n"
        )
        for tf, ind in ind_summary.items():
            context += f"\n### {tf}\n"
            for k, v in ind.items():
                context += f"- {k}: {v}\n"

        prompt = (
            "请检查技术指标是否支持趋势判断：\n"
            "1. RSI在多周期是否超买/超卖？是否与趋势矛盾？\n"
            "2. MACD交叉信号在多周期是否一致？\n"
            "3. 布林带位置是否确认趋势？\n"
            "4. KDJ是否出现背离信号？\n"
            "5. 成交量是否支持当前趋势？\n"
            "6. 标记所有指标间的矛盾"
        )

        step = await self._run_reasoning_step("indicator_consensus", prompt, context)
        step.step_id = 2
        return step

    async def _reason_multi_timeframe(
        self, symbol: str, indicators: dict, chart_analyses: dict
    ) -> ReasoningStep:
        """Step 3: 多周期交叉验证"""
        context = f"品种: {symbol}\n\n"
        for tf, analysis in chart_analyses.items():
            context += f"### {tf} 图表视觉分析\n{analysis[:500]}\n\n"

        for tf, ind in indicators.items():
            context += f"### {tf} 技术指标快照\n"
            context += f"- 趋势: {ind.get('trend')} | RSI: {ind.get('rsi')} | MACD交叉: {ind.get('macd_cross')}\n\n"

        prompt = (
            "请进行多周期交叉验证：\n"
            "1. 短期(1H)、中期(4H)、长期(1D/1W)趋势是否共振？\n"
            "2. 不同周期的支撑阻力位是否重合？\n"
            "3. 图表视觉分析与指标计算结果是否一致？\n"
            "4. 如果存在周期冲突，哪个周期更可靠？\n"
            "5. 多周期共振的强度如何？"
        )

        step = await self._run_reasoning_step("multi_timeframe", prompt, context)
        step.step_id = 3
        return step

    async def _reason_news_sentiment(
        self, symbol: str, news_sentiment: dict, trend_step: ReasoningStep
    ) -> ReasoningStep:
        """Step 4: 新闻情绪融合"""
        mimo_analysis = news_sentiment.get("mimo_analysis", "无新闻数据")
        fear_greed = news_sentiment.get("fear_greed", {})
        news_count = len(news_sentiment.get("news", []))

        context = (
            f"品种: {symbol}\n"
            f"趋势判断: {trend_step.conclusion}\n"
            f"新闻分析(MiMo): {mimo_analysis[:1000]}\n"
            f"恐慌贪婪指数: {fear_greed.get('value', 'N/A')} ({fear_greed.get('classification', 'N/A')})\n"
            f"新闻数量: {news_count}条\n"
        )

        prompt = (
            "请融合新闻情绪与趋势判断：\n"
            "1. 新闻面是否支持技术面趋势？\n"
            "2. 恐慌贪婪指数是否极端？极端值可能意味着反转？\n"
            "3. 是否有重大事件可能导致趋势突变？\n"
            "4. 新闻情绪是否存在滞后或提前反应？\n"
            "5. 综合技术面+消息面，趋势可靠性如何？"
        )

        step = await self._run_reasoning_step("news_sentiment", prompt, context)
        step.step_id = 4
        return step

    async def _reason_final(
        self, symbol: str, prev_steps: list[ReasoningStep], market_data: dict
    ) -> ReasoningStep:
        """Step 5: 最终综合推理"""
        steps_summary = ""
        for s in prev_steps:
            steps_summary += (
                f"- {s.name}: {s.conclusion} (置信度: {s.confidence:.0%})\n"
            )
            if s.contradictions:
                steps_summary += f"  矛盾: {'; '.join(s.contradictions)}\n"

        context = (
            f"品种: {symbol}\n"
            f"当前价格: {market_data.get('price', 'N/A')}\n\n"
            f"前序推理步骤总结:\n{steps_summary}\n"
            f"发现的矛盾:\n"
        )
        for s in prev_steps:
            for c in s.contradictions:
                context += f"- [{s.name}] {c}\n"

        prompt = (
            "请基于以上所有推理步骤，给出最终综合分析：\n"
            "1. 综合所有步骤的结论，最终方向判断是什么？\n"
            "2. 如何解释发现的矛盾？矛盾是否足以推翻结论？\n"
            "3. 综合置信度评估（考虑矛盾的影响）\n"
            "4. 给出具体的操作建议（方向、入场、止损、止盈、杠杆）\n"
            "5. 标注最大风险和不确定性来源"
        )

        step = await self._run_reasoning_step("risk_assessment", prompt, context)
        step.step_id = 5
        return step

    @staticmethod
    def _extract_section(text: str, label: str) -> str:
        """提取标记段落"""
        patterns = [
            rf"{label}:\s*(.+?)(?=\n[A-Z_]+:|$)",
            rf"{label}\s*[:：]\s*(.+?)(?=\n\n|\n[A-Z]|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_confidence(text: str) -> float:
        """提取置信度"""
        match = re.search(r'CONFIDENCE:\s*(\d+)\s*%?', text, re.IGNORECASE)
        if match:
            return int(match.group(1)) / 100.0
        match = re.search(r'置信度[:\s]*(\d+)\s*%?', text)
        if match:
            return int(match.group(1)) / 100.0
        return 0.5

    @staticmethod
    def _extract_contradictions(text: str) -> list[str]:
        """提取矛盾列表"""
        section = CoTEngine._extract_section(text, "CONTRADICTIONS")
        if not section or section.lower() in ("none", "无", "n/a", ""):
            return []
        items = re.split(r'[;；\n]', section)
        return [item.strip() for item in items if item.strip() and item.strip().lower() not in ("none", "无")]
