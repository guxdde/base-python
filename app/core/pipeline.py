from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    success: bool
    message: str
    data: Optional[dict] = None


class PipelineStep(ABC):
    name: str = ""
    target_state: Optional[str] = None
    optional: bool = True

    @abstractmethod
    async def can_execute(self, record: Any, context: dict) -> bool:
        pass

    @abstractmethod
    async def execute(self, record: Any, context: dict) -> StepResult:
        pass

    def get_required_state(self) -> Optional[str]:
        return None


class Pipeline:
    def __init__(self, name: str, steps: list[PipelineStep]):
        self.name = name
        self.steps = steps

    async def execute(self, record: Any, context: dict) -> dict:
        results = []

        for step in self.steps:
            try:
                if not await step.can_execute(record, context):
                    logger.debug(f"跳过步骤: {step.name}, 状态不满足")
                    continue

                logger.info(f"执行步骤: {step.name}")
                result = await step.execute(record, context)

                results.append({
                    "step": step.name,
                    "success": result.success,
                    "message": result.message,
                    "data": result.data
                })

                if result.success and step.target_state:
                    record.process_status = step.target_state
                    await context["db"].commit()
                    logger.info(f"状态更新: {step.name} -> {step.target_state}")

                if not result.success and not step.optional:
                    logger.error(f"必需步骤失败: {step.name}, {result.message}")
                    break

            except Exception as e:
                logger.exception(f"步骤执行异常: {step.name}")
                results.append({
                    "step": step.name,
                    "success": False,
                    "message": str(e)
                })
                if not step.optional:
                    break

        completed_steps = [r for r in results if r["success"]]
        return {
            "pipeline": self.name,
            "completed": all(r["success"] for r in results) if results else False,
            "steps_executed": len(completed_steps),
            "total_steps": len(self.steps),
            "results": results
        }
