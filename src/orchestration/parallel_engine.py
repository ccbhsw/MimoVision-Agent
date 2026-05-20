"""
并行执行引擎
多Agent并行执行 + 结果聚合
"""
import asyncio
import logging
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from src.utils.mimo_client import MiMoClient, MiMoMessage

logger = logging.getLogger(__name__)


@dataclass
class TaskSpec:
    """并行任务规格"""
    name: str
    coro: Any  # coroutine or callable
    priority: int = 0  # 0=最高
    timeout: int = 120
    retries: int = 2
    required: bool = True  # True=失败则整体失败


@dataclass
class TaskResult:
    """并行任务结果"""
    name: str
    success: bool
    result: Any = None
    error: str = ""
    duration_ms: float = 0.0
    attempts: int = 1


class ParallelEngine:
    """
    并行执行引擎

    特性：
    - 多任务并行执行
    - 优先级调度
    - 超时控制
    - 自动重试
    - 结果聚合
    - 部分失败容忍
    """

    def __init__(self, mimo_client: MiMoClient, max_concurrency: int = 5):
        self.mimo = mimo_client
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._results: dict[str, TaskResult] = {}

    async def execute_parallel(
        self,
        tasks: list[TaskSpec],
        fail_fast: bool = False,
    ) -> dict[str, TaskResult]:
        """
        并行执行多个任务

        Args:
            tasks: 任务列表
            fail_fast: 是否在第一个失败时立即停止

        Returns:
            {task_name: TaskResult}
        """
        self._results = {}

        # 按优先级排序
        sorted_tasks = sorted(tasks, key=lambda t: t.priority)

        async def run_task(spec: TaskSpec) -> TaskResult:
            async with self._semaphore:
                return await self._run_with_retry(spec)

        coros = [run_task(spec) for spec in sorted_tasks]

        if fail_fast:
            results = await asyncio.gather(*coros, return_exceptions=False)
        else:
            results = await asyncio.gather(*coros, return_exceptions=True)

        for spec, result in zip(sorted_tasks, results):
            if isinstance(result, Exception):
                self._results[spec.name] = TaskResult(
                    name=spec.name, success=False, error=str(result),
                )
            else:
                self._results[spec.name] = result

        return self._results

    async def execute_stages(
        self,
        stages: list[list[TaskSpec]],
    ) -> list[dict[str, TaskResult]]:
        """
        分阶段执行：每阶段内的任务并行，阶段间串行

        Args:
            stages: [[stage1_tasks], [stage2_tasks], ...]

        Returns:
            [stage1_results, stage2_results, ...]
        """
        all_results = []

        for stage_idx, stage_tasks in enumerate(stages):
            logger.info(f"Stage {stage_idx}: executing {len(stage_tasks)} tasks")
            results = await self.execute_parallel(stage_tasks)
            all_results.append(results)

            # 检查是否有必须任务失败
            for name, result in results.items():
                spec = next((t for t in stage_tasks if t.name == name), None)
                if spec and spec.required and not result.success:
                    logger.error(f"Stage {stage_idx} required task '{name}' failed, aborting")
                    return all_results

        return all_results

    async def execute_multi_model_analysis(
        self,
        symbol: str,
        analysis_tasks: dict[str, str],
        models: list[str] = None,
    ) -> dict:
        """
        多模型并行分析同一任务

        Args:
            symbol: 交易对
            analysis_tasks: {task_name: prompt}
            models: 使用的模型列表

        Returns:
            {task_name: {model: response_content}}
        """
        models = models or ["mimo-v2.5-pro", "mimo-v2-flash"]

        tasks = []
        for task_name, prompt in analysis_tasks.items():
            for model in models:
                tasks.append(TaskSpec(
                    name=f"{task_name}_{model.replace('.', '_')}",
                    coro=self._chat(model, prompt, symbol),
                    timeout=90,
                ))

        results = await self.execute_parallel(tasks)

        # 重组结果
        organized = {}
        for task_name in analysis_tasks:
            organized[task_name] = {}
            for model in models:
                key = f"{task_name}_{model.replace('.', '_')}"
                if key in results and results[key].success:
                    organized[task_name][model] = results[key].result

        return organized

    async def _run_with_retry(self, spec: TaskSpec) -> TaskResult:
        """带重试的任务执行"""
        start = datetime.now()
        last_error = ""

        for attempt in range(1, spec.retries + 1):
            try:
                result = await asyncio.wait_for(
                    spec.coro if asyncio.iscoroutine(spec.coro) else await spec.coro,
                    timeout=spec.timeout,
                )
                duration = (datetime.now() - start).total_seconds() * 1000
                return TaskResult(
                    name=spec.name,
                    success=True,
                    result=result,
                    duration_ms=round(duration, 1),
                    attempts=attempt,
                )
            except asyncio.TimeoutError:
                last_error = f"Timeout after {spec.timeout}s"
                logger.warning(f"Task {spec.name} timeout (attempt {attempt})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Task {spec.name} failed (attempt {attempt}): {e}")

            if attempt < spec.retries:
                await asyncio.sleep(1 * attempt)

        duration = (datetime.now() - start).total_seconds() * 1000
        return TaskResult(
            name=spec.name,
            success=False,
            error=last_error,
            duration_ms=round(duration, 1),
            attempts=spec.retries,
        )

    async def _chat(self, model: str, prompt: str, symbol: str):
        """快捷聊天方法"""
        messages = [
            MiMoMessage(role="system", content=f"你是{symbol}的金融分析专家。"),
            MiMoMessage(role="user", content=prompt),
        ]
        response = await self.mimo.chat(
            messages=messages, model=model,
            temperature=0.3, max_tokens=2000,
        )
        return response.content

    def get_summary(self) -> dict:
        """获取执行摘要"""
        total = len(self._results)
        success = sum(1 for r in self._results.values() if r.success)
        return {
            "total_tasks": total,
            "successful": success,
            "failed": total - success,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
            "total_time_ms": sum(r.duration_ms for r in self._results.values()),
            "failed_tasks": [
                {"name": r.name, "error": r.error}
                for r in self._results.values() if not r.success
            ],
        }
