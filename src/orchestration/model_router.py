"""
多模型智能路由器
根据任务复杂度自动选择 MiMo-V2.5-Pro / MiMo-V2-Omni / MiMo-V2-Flash
"""
import logging
import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from src.utils.mimo_client import MiMoClient, MiMoMessage

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    MULTIMODAL = "multimodal"
    AUDIO = "audio"


@dataclass
class RouterDecision:
    """路由决策"""
    task_type: str
    complexity: TaskComplexity
    selected_model: str
    reason: str
    estimated_tokens: int
    fallback_model: str = ""
    timestamp: str = ""


class ModelRouter:
    """
    多模型智能路由器

    路由规则：
    - 简单查询(价格查询、快速扫描) → MiMo-V2-Flash
    - 中等复杂(情绪分析、单指标解读) → MiMo-V2-Flash 或 MiMo-V2.5-Pro
    - 高复杂(策略推理、多维度综合) → MiMo-V2.5-Pro
    - 多模态(图表分析、图片理解) → MiMo-V2-Omni
    - 音频(播客、语音分析) → MiMo-V2-Omni
    """

    COMPLEXITY_KEYWORDS = {
        TaskComplexity.SIMPLE: [
            "价格", "price", "查询", "query", "最新", "current",
            "简单", "quick", "fast",
        ],
        TaskComplexity.MODERATE: [
            "情绪", "sentiment", "新闻", "news", "分析", "analysis",
            "指标", "indicator", "评分", "score",
        ],
        TaskComplexity.COMPLEX: [
            "策略", "strategy", "推理", "reasoning", "综合", "comprehensive",
            "交易", "trade", "建议", "recommendation", "深度", "deep",
            "回测", "backtest", "组合", "portfolio", "优化", "optimize",
        ],
        TaskComplexity.MULTIMODAL: [
            "图表", "chart", "图片", "image", "K线", "candlestick",
            "视觉", "visual", "形态", "pattern", "截图", "screenshot",
        ],
        TaskComplexity.AUDIO: [
            "音频", "audio", "语音", "voice", "播客", "podcast",
            "视频", "video",
        ],
    }

    MODEL_MAP = {
        TaskComplexity.SIMPLE: "mimo-v2-flash",
        TaskComplexity.MODERATE: "mimo-v2-flash",
        TaskComplexity.COMPLEX: "mimo-v2.5-pro",
        TaskComplexity.MULTIMODAL: "mimo-v2-omni",
        TaskComplexity.AUDIO: "mimo-v2-omni",
    }

    FALLBACK_MAP = {
        "mimo-v2.5-pro": "mimo-v2-flash",
        "mimo-v2-omni": "mimo-v2.5-pro",
        "mimo-v2-flash": "mimo-v2-flash",
    }

    TOKEN_ESTIMATES = {
        TaskComplexity.SIMPLE: 500,
        TaskComplexity.MODERATE: 2000,
        TaskComplexity.COMPLEX: 4000,
        TaskComplexity.MULTIMODAL: 3000,
        TaskComplexity.AUDIO: 2500,
    }

    def __init__(self, mimo_client: MiMoClient):
        self.mimo = mimo_client
        self._decision_history: list[RouterDecision] = []

    def route(self, task_description: str, has_image: bool = False, has_audio: bool = False) -> RouterDecision:
        """
        根据任务描述自动选择最佳模型

        Args:
            task_description: 任务描述文本
            has_image: 是否包含图片
            has_audio: 是否包含音频

        Returns:
            RouterDecision 路由决策
        """
        # 多模态优先判断
        if has_audio:
            complexity = TaskComplexity.AUDIO
        elif has_image:
            complexity = TaskComplexity.MULTIMODAL
        else:
            complexity = self._assess_complexity(task_description)

        model = self.MODEL_MAP[complexity]
        fallback = self.FALLBACK_MAP[model]
        est_tokens = self.TOKEN_ESTIMATES[complexity]

        decision = RouterDecision(
            task_type=task_description[:100],
            complexity=complexity,
            selected_model=model,
            reason=self._get_reason(complexity, model),
            estimated_tokens=est_tokens,
            fallback_model=fallback,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._decision_history.append(decision)
        return decision

    async def route_and_execute(
        self,
        messages: list[MiMoMessage],
        task_description: str,
        has_image: bool = False,
        has_audio: bool = False,
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> tuple:
        """
        路由并执行，失败自动fallback

        Returns:
            (MiMoResponse, RouterDecision)
        """
        decision = self.route(task_description, has_image, has_audio)

        try:
            response = await self.mimo.chat(
                messages=messages,
                model=decision.selected_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response, decision
        except Exception as e:
            logger.warning(
                f"Model {decision.selected_model} failed: {e}, "
                f"falling back to {decision.fallback_model}"
            )
            if decision.fallback_model != decision.selected_model:
                response = await self.mimo.chat(
                    messages=messages,
                    model=decision.fallback_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response, decision
            raise

    async def execute_multi_model_consensus(
        self,
        messages: list[MiMoMessage],
        models: list[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 3000,
    ) -> dict:
        """
        多模型共识：同时让多个模型回答，对比结果

        Returns:
            {
                "responses": {model: MiMoResponse},
                "consensus_direction": str,
                "agreement_pct": float,
                "best_response": MiMoResponse,
            }
        """
        models = models or ["mimo-v2.5-pro", "mimo-v2-flash"]
        import asyncio

        tasks = {
            model: self.mimo.chat(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens,
            )
            for model in models
        }

        results = {}
        for model, task in tasks.items():
            try:
                results[model] = await task
            except Exception as e:
                logger.warning(f"Model {model} failed in consensus: {e}")

        if not results:
            raise Exception("All models failed in consensus")

        # 分析共识
        directions = {}
        for model, resp in results.items():
            text = resp.content.lower()
            if "做多" in resp.content or "long" in text or "买入" in resp.content:
                d = "long"
            elif "做空" in resp.content or "short" in text or "卖出" in resp.content:
                d = "short"
            else:
                d = "wait"
            directions[model] = d

        # 计算一致性
        dir_counts = {}
        for d in directions.values():
            dir_counts[d] = dir_counts.get(d, 0) + 1
        best_dir = max(dir_counts, key=dir_counts.get)
        agreement = dir_counts[best_dir] / len(directions)

        # 选择Pro模型的结果作为best
        best_model = "mimo-v2.5-pro" if "mimo-v2.5-pro" in results else list(results.keys())[0]

        return {
            "responses": results,
            "directions": directions,
            "consensus_direction": best_dir,
            "agreement_pct": round(agreement * 100, 1),
            "best_response": results[best_model],
        }

    def _assess_complexity(self, text: str) -> TaskComplexity:
        """评估任务复杂度"""
        scores = {tc: 0 for tc in TaskComplexity}
        text_lower = text.lower()

        for tc, keywords in self.COMPLEXITY_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[tc] += 1

        # 从高到低优先
        priority = [
            TaskComplexity.AUDIO,
            TaskComplexity.MULTIMODAL,
            TaskComplexity.COMPLEX,
            TaskComplexity.MODERATE,
            TaskComplexity.SIMPLE,
        ]
        for tc in priority:
            if scores[tc] > 0:
                return tc
        return TaskComplexity.MODERATE

    def _get_reason(self, complexity: TaskComplexity, model: str) -> str:
        reasons = {
            TaskComplexity.SIMPLE: "简单查询，Flash模型足够",
            TaskComplexity.MODERATE: "中等复杂任务，Flash可高效处理",
            TaskComplexity.COMPLEX: "高复杂推理任务，需要Pro模型的深度能力",
            TaskComplexity.MULTIMODAL: "多模态任务，需要Omni模型的视觉理解",
            TaskComplexity.AUDIO: "音频分析任务，需要Omni模型的音频能力",
        }
        return reasons.get(complexity, "")

    def get_routing_stats(self) -> dict:
        """获取路由统计"""
        if not self._decision_history:
            return {}
        model_counts = {}
        for d in self._decision_history:
            model_counts[d.selected_model] = model_counts.get(d.selected_model, 0) + 1
        return {
            "total_decisions": len(self._decision_history),
            "model_distribution": model_counts,
            "recent_decisions": [
                {
                    "task": d.task_type[:50],
                    "model": d.selected_model,
                    "complexity": d.complexity.value,
                }
                for d in self._decision_history[-10:]
            ],
        }
