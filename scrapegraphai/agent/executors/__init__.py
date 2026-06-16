"""
Executor engine for GraphSpider Agent.
"""

from .base_executor import AbstractExecutor, ExecutionResult
from .local_executor import LocalExecutor
from ..config import ExecutionMode


class ExecutorFactory:
    """Create the right executor based on execution mode."""

    @staticmethod
    def create(mode: ExecutionMode) -> AbstractExecutor:
        if mode == ExecutionMode.LOCAL:
            return LocalExecutor()
        # Future: Docker, E2B
        raise ValueError(f"Unsupported execution mode: {mode}")


__all__ = [
    "AbstractExecutor",
    "ExecutionResult",
    "LocalExecutor",
    "ExecutorFactory",
    "ExecutionMode",
]
