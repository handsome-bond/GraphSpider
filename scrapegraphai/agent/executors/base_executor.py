"""
Abstract base executor — all executors conform to this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


class AbstractExecutor(ABC):
    """Execute a Python scraper script and return structured results."""

    @abstractmethod
    def execute(self, script: str, timeout: int = 60) -> ExecutionResult:
        ...
