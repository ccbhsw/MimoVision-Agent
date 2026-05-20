"""
推理链验证引擎
对推理结果进行自我验证、一致性检查、逻辑审计
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
class VerificationResult:
    """验证结果"""
    step_name: str
    passed: bool
    score: float  # 0-100
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    verified_at: str = ""


class VerificationEngine:
    """
    推理验证引擎

    验证维度：
    1. 内部一致性 — 各推理步骤之间是否矛盾
    2. 数据一致性 — 推理结论是否与原始数据匹配
    3. 逻辑完整性 — 是否有逻辑跳跃或遗漏
    4. 常识检查 — 结论是否违背基本常识
    5. 置信度校准 — 置信度是否合理
    """

    VERIFICATION_PROMPT = (
        "你是一个严谨的金融分析审计师。你的任务是检查分析结论的质量。\n"
        "请从以下维度评估：\n"
        "1. INTERNAL_CONSISTENCY: 各分析步骤之间是否存在矛盾 (0-100)\n"
        "2. DATA_ALIGNMENT: 结论是否与提供的数据匹配 (0-100)\n"
        "3. LOGIC_COMPLETENESS: 推理链是否有跳跃或遗漏 (0-100)\n"
        "4. COMMON_SENSE: 结论是否违背基本常识 (0-100)\n"
        "5. CONFIDENCE_CALIBRATION: 置信度是否合理 (0-100)\n\n"
        "严格格式：\n"
        "INTERNAL_CONSISTENCY: XX\n"
        "DATA_ALIGNMENT: XX\n"
        "LOGIC_COMPLETENESS: XX\n"
        "COMMON_SENSE: XX\n"
        "CONFIDENCE_CALIBRATION: XX\n"
        "OVERALL_SCORE: XX\n"
        "ISSUES: ...\n"
        "SUGGESTIONS: ...\n"
        "PASS: yes/no"
    )

    def __init__(self, mimo_client: MiMoClient):
        self.mimo = mimo_client

    async def verify_chain(
        self,
        reasoning_text: str,
        market_data: dict,
        technical_indicators: dict,
        final_direction: str,
        final_confidence: float,
    ) -> VerificationResult:
        """验证完整推理链"""
        data_summary = (
            f"价格: {market_data.get('price', 'N/A')}\n"
            f"24h涨跌: {market_data.get('change_24h', 'N/A')}%\n"
            f"资金费率: {market_data.get('funding_rate', 'N/A')}\n"
        )
        for tf, ind in technical_indicators.items():
            data_summary += (
                f"\n{tf}: 趋势={ind.get('trend')} RSI={ind.get('rsi')} "
                f"MACD交叉={ind.get('macd_cross')}"
            )

        user_content = (
            f"## 原始数据\n{data_summary}\n\n"
            f"## 分析推理\n{reasoning_text[:3000]}\n\n"
            f"## 最终结论\n"
            f"方向: {final_direction}\n"
            f"置信度: {final_confidence:.0%}\n\n"
            "请验证以上分析的质量和一致性。"
        )

        messages = [
            MiMoMessage(role="system", content=self.VERIFICATION_PROMPT),
            MiMoMessage(role="user", content=user_content),
        ]

        response = await self.mimo.chat(
            messages=messages,
            model="mimo-v2.5-pro",
            temperature=0.2,
            max_tokens=2000,
        )

        return self._parse_verification(response.content)

    async def verify_direction(
        self,
        direction: str,
        indicators: dict[str, dict],
    ) -> VerificationResult:
        """验证方向判断是否与技术指标一致"""
        bullish_signals = 0
        bearish_signals = 0
        total_signals = 0

        for tf, ind in indicators.items():
            trend = ind.get("trend", "ranging")
            if trend == "bullish":
                bullish_signals += 1
            elif trend == "bearish":
                bearish_signals += 1

            rsi = ind.get("rsi", 50)
            if rsi > 60:
                bullish_signals += 0.5
            elif rsi < 40:
                bearish_signals += 0.5

            macd_cross = ind.get("macd_cross", "none")
            if macd_cross == "bullish":
                bullish_signals += 1
            elif macd_cross == "bearish":
                bearish_signals += 1

            total_signals += 2.5

        if direction == "long":
            score = (bullish_signals / total_signals * 100) if total_signals > 0 else 50
        elif direction == "short":
            score = (bearish_signals / total_signals * 100) if total_signals > 0 else 50
        else:
            score = 50

        issues = []
        if direction == "long" and bearish_signals > bullish_signals:
            issues.append("做多方向与多数指标看空矛盾")
        if direction == "short" and bullish_signals > bearish_signals:
            issues.append("做空方向与多数指标看多矛盾")

        passed = score > 50 and len(issues) == 0

        return VerificationResult(
            step_name="direction_verification",
            passed=passed,
            score=round(score, 1),
            issues=issues,
            suggestions=["考虑等待更多确认信号"] if not passed else [],
            verified_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def verify_risk_params(
        self,
        entry: float,
        stop_loss: float,
        take_profit: float,
        leverage: int,
        atr: float,
        direction: str,
        account_balance: float,
    ) -> VerificationResult:
        """验证风险参数的合理性"""
        issues = []
        suggestions = []

        # 检查止损距离
        if direction == "long":
            sl_distance = entry - stop_loss
            tp_distance = take_profit - entry
        else:
            sl_distance = stop_loss - entry
            tp_distance = entry - take_profit

        if sl_distance <= 0:
            issues.append(f"止损方向错误: entry={entry}, sl={stop_loss}, dir={direction}")
        if tp_distance <= 0:
            issues.append(f"止盈方向错误: entry={entry}, tp={take_profit}, dir={direction}")

        # ATR合理性检查
        if atr > 0 and sl_distance > 0:
            sl_atr_ratio = sl_distance / atr
            if sl_atr_ratio > 5:
                issues.append(f"止损过宽: {sl_atr_ratio:.1f}倍ATR (建议2-3倍)")
                suggestions.append("缩小止损到2-3倍ATR")
            elif sl_atr_ratio < 0.5:
                issues.append(f"止损过窄: {sl_atr_ratio:.1f}倍ATR (容易被噪音触发)")
                suggestions.append("放宽止损到至少1.5倍ATR")

        # 盈亏比检查
        if sl_distance > 0 and tp_distance > 0:
            rr = tp_distance / sl_distance
            if rr < 1.0:
                issues.append(f"盈亏比过低: {rr:.2f} (建议至少1.5)")
                suggestions.append("扩大止盈或缩小止损")
        else:
            rr = 0

        # 杠杆检查
        if leverage > 50:
            issues.append(f"杠杆过高: {leverage}x (建议不超过30x)")
            suggestions.append("降低杠杆到合理范围")
        if leverage > 20 and sl_distance > 0:
            max_loss_pct = (sl_distance / entry) * leverage * 100
            if max_loss_pct > 30:
                issues.append(f"最大单笔亏损: {max_loss_pct:.1f}% (过高)")
                suggestions.append(f"降低杠杆到{max(1, int(30 / ((sl_distance / entry) * 100)))}x以下")

        # 保证金检查
        position_value = account_balance * 0.15  # 假设15%仓位
        margin = position_value / leverage
        liquidation_distance = (1 / leverage) * 100
        if liquidation_distance < (sl_distance / entry * 100):
            issues.append(f"强平价可能在止损之内")

        score = max(0, 100 - len(issues) * 20)
        passed = len(issues) <= 1 and score >= 60

        return VerificationResult(
            step_name="risk_params_verification",
            passed=passed,
            score=score,
            issues=issues,
            suggestions=suggestions,
            verified_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _parse_verification(self, text: str) -> VerificationResult:
        """解析验证结果"""
        scores = {}
        for label in [
            "INTERNAL_CONSISTENCY", "DATA_ALIGNMENT",
            "LOGIC_COMPLETENESS", "COMMON_SENSE",
            "CONFIDENCE_CALIBRATION", "OVERALL_SCORE",
        ]:
            match = re.search(rf'{label}:\s*(\d+)', text, re.IGNORECASE)
            scores[label] = int(match.group(1)) if match else 50

        issues_section = self._extract_section(text, "ISSUES")
        suggestions_section = self._extract_section(text, "SUGGESTIONS")

        issues = [i.strip() for i in re.split(r'[;；\n]', issues_section) if i.strip()] if issues_section else []
        suggestions = [s.strip() for s in re.split(r'[;；\n]', suggestions_section) if s.strip()] if suggestions_section else []

        pass_match = re.search(r'PASS:\s*(yes|no)', text, re.IGNORECASE)
        passed = pass_match.group(1).lower() == "yes" if pass_match else scores["OVERALL_SCORE"] >= 60

        return VerificationResult(
            step_name="full_chain_verification",
            passed=passed,
            score=scores.get("OVERALL_SCORE", 50),
            issues=issues,
            suggestions=suggestions,
            verified_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    @staticmethod
    def _extract_section(text: str, label: str) -> str:
        match = re.search(rf'{label}:\s*(.+?)(?=\n[A-Z_]+:|$)', text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""
