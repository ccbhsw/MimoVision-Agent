"""
Pipeline 编排器
支持串行、并行、DAG式任务编排
"""
import asyncio
import logging
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.utils.mimo_client import MiMoClient, MiMoMessage
from src.orchestration.model_router import ModelRouter, TaskComplexity

logger = logging.getLogger(__name__)


class StepType(Enum):
    SERIAL = "serial"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


@dataclass
class PipelineStep:
    """Pipeline步骤定义"""
    name: str
    step_type: StepType
    prompt_template: str
    model: str = ""
    temperature: float = 0.4
    max_tokens: int = 3000
    depends_on: list[str] = field(default_factory=list)
    condition_key: str = ""
    condition_value: str = ""
    timeout: int = 120


@dataclass
class StepResult:
    """步骤执行结果"""
    name: str
    success: bool
    output: str = ""
    model_used: str = ""
    tokens_used: int = 0
    duration_ms: float = 0.0
    error: str = ""


class Pipeline:
    """
    Pipeline 编排器

    支持三种编排模式：
    1. 串行 — 步骤按顺序执行，前一步的输出作为后一步的输入
    2. 并行 — 多个步骤同时执行
    3. DAG — 带依赖关系的有向无环图
    """

    # 预定义的分析Pipeline
    FULL_ANALYSIS_PIPELINE = [
        PipelineStep(
            name="data_collection",
            step_type=StepType.PARALLEL,
            prompt_template="采集{symbol}的市场数据",
            model="mimo-v2-flash",
            max_tokens=1000,
        ),
        PipelineStep(
            name="technical_analysis",
            step_type=StepType.SERIAL,
            prompt_template="基于采集到的数据，计算技术指标",
            model="mimo-v2-flash",
            depends_on=["data_collection"],
            max_tokens=2000,
        ),
        PipelineStep(
            name="chart_visual_analysis",
            step_type=StepType.PARALLEL,
            prompt_template="分析{symbol}的K线图表",
            model="mimo-v2-omni",
            depends_on=["data_collection"],
            max_tokens=3000,
        ),
        PipelineStep(
            name="news_sentiment",
            step_type=StepType.PARALLEL,
            prompt_template="分析{symbol}相关新闻的情绪",
            model="mimo-v2-flash",
            max_tokens=2000,
        ),
        PipelineStep(
            name="strategy_reasoning",
            step_type=StepType.SERIAL,
            prompt_template="基于所有分析结果，生成交易策略",
            model="mimo-v2.5-pro",
            depends_on=["technical_analysis", "chart_visual_analysis", "news_sentiment"],
            temperature=0.3,
            max_tokens=4000,
        ),
        PipelineStep(
            name="risk_assessment",
            step_type=StepType.SERIAL,
            prompt_template="评估策略的风险并给出仓位建议",
            model="mimo-v2.5-pro",
            depends_on=["strategy_reasoning"],
            temperature=0.2,
            max_tokens=2000,
        ),
    ]

    def __init__(self, mimo_client: MiMoClient):
        self.mimo = mimo_client
        self.router = ModelRouter(mimo_client)
        self._results: dict[str, StepResult] = {}
        self._execution_log: list[dict] = []

    async def execute(
        self,
        steps: list[PipelineStep],
        context: dict,
    ) -> dict[str, StepResult]:
        """
        执行Pipeline

        Args:
            steps: 步骤列表
            context: 共享上下文（symbol, market_data等）

        Returns:
            {step_name: StepResult}
        """
        self._results = {}
        executed = set()

        # 按依赖拓扑排序
        sorted_steps = self._topological_sort(steps)

        # 分层执行（同层可并行）
        layers = self._build_layers(sorted_steps)

        for layer_idx, layer in enumerate(layers):
            logger.info(f"Pipeline Layer {layer_idx}: {[s.name for s in layer]}")

            tasks = []
            for step in layer:
                # 检查条件
                if step.step_type == StepType.CONDITIONAL:
                    if context.get(step.condition_key) != step.condition_value:
                        continue

                # 构建prompt
                prompt = step.prompt_template.format(**{k: str(v) for k, v in context.items()})

                # 如果有依赖，注入前序结果
                if step.depends_on:
                    dep_results = []
                    for dep_name in step.depends_on:
                        if dep_name in self._results:
                            dep_results.append(
                                f"[{dep_name}]: {self._results[dep_name].output[:1000]}"
                            )
                    if dep_results:
                        prompt += "\n\n前序分析结果:\n" + "\n".join(dep_results)

                tasks.append(self._execute_step(step, prompt))

            # 并行执行同层
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(layer, results):
                if isinstance(result, Exception):
                    self._results[step.name] = StepResult(
                        name=step.name, success=False, error=str(result),
                    )
                    logger.error(f"Step {step.name} failed: {result}")
                else:
                    self._results[step.name] = result

                executed.add(step.name)
                self._execution_log.append({
                    "step": step.name,
                    "success": self._results[step.name].success,
                    "model": self._results[step.name].model_used,
                    "timestamp": datetime.now().isoformat(),
                })

        return self._results

    async def _execute_step(self, step: PipelineStep, prompt: str) -> StepResult:
        """执行单个步骤"""
        start = datetime.now()
        model = step.model or "mimo-v2-flash"

        messages = [
            MiMoMessage(role="system", content="你是专业的金融分析助手。"),
            MiMoMessage(role="user", content=prompt),
        ]

        try:
            response = await asyncio.wait_for(
                self.mimo.chat(
                    messages=messages,
                    model=model,
                    temperature=step.temperature,
                    max_tokens=step.max_tokens,
                ),
                timeout=step.timeout,
            )

            duration = (datetime.now() - start).total_seconds() * 1000

            return StepResult(
                name=step.name,
                success=True,
                output=response.content,
                model_used=response.model,
                tokens_used=response.usage.get("total_tokens", 0),
                duration_ms=round(duration, 1),
            )
        except asyncio.TimeoutError:
            return StepResult(
                name=step.name, success=False,
                error=f"Timeout after {step.timeout}s",
            )
        except Exception as e:
            return StepResult(name=step.name, success=False, error=str(e))

    def _topological_sort(self, steps: list[PipelineStep]) -> list[PipelineStep]:
        """拓扑排序"""
        name_map = {s.name: s for s in steps}
        visited = set()
        order = []

        def visit(name: str):
            if name in visited:
                return
            visited.add(name)
            if name in name_map:
                for dep in name_map[name].depends_on:
                    visit(dep)
                order.append(name_map[name])

        for s in steps:
            visit(s.name)
        return order

    def _build_layers(self, sorted_steps: list[PipelineStep]) -> list[list[PipelineStep]]:
        """将排序后的步骤分成可并行的层"""
        layers = []
        current_layer = []
        completed_in_prev = set()

        for step in sorted_steps:
            if not step.depends_on or all(d in completed_in_prev for d in step.depends_on):
                current_layer.append(step)
            else:
                if current_layer:
                    layers.append(current_layer)
                layers.append([step])
                completed_in_prev.add(step.name)
                current_layer = []

            completed_in_prev.add(step.name)

        if current_layer:
            layers.append(current_layer)

        return layers

    def get_execution_summary(self) -> dict:
        """获取执行摘要"""
        total = len(self._results)
        success = sum(1 for r in self._results.values() if r.success)
        total_tokens = sum(r.tokens_used for r in self._results.values())
        total_time = sum(r.duration_ms for r in self._results.values())

        return {
            "total_steps": total,
            "successful": success,
            "failed": total - success,
            "total_tokens": total_tokens,
            "total_time_ms": round(total_time, 1),
            "steps": {
                name: {
                    "success": r.success,
                    "model": r.model_used,
                    "tokens": r.tokens_used,
                    "time_ms": r.duration_ms,
                }
                for name, r in self._results.items()
            },
        }
