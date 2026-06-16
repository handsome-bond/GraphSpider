"""
LocalExecutor — runs scraper scripts via subprocess on the host machine.
"""

import os
import subprocess
import tempfile

from .base_executor import AbstractExecutor, ExecutionResult


class LocalExecutor(AbstractExecutor):
    """Execute a script in a local subprocess with a timeout."""

    def execute(self, script: str, timeout: int = 60) -> ExecutionResult:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(script)
                tmp_path = f.name

            proc = subprocess.run(
                ["python", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                exit_code=proc.returncode,
                timed_out=False,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                stdout="",
                stderr="Execution timed out",
                exit_code=-1,
                timed_out=True,
            )
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # Reserved — future sandboxed implementations
    # docker_executor.py, e2b_cloud_executor.py
