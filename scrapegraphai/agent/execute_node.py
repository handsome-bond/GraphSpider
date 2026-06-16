"""
Execute node — runs the generated scraper script in a sandbox.
"""

from .executors import ExecutorFactory
from .config import ExecutionMode
from .state.autonomous_state import AutonomousState


def execute_node(state: AutonomousState) -> AutonomousState:
    """Run the current script and capture stdout / stderr."""
    config = state.get("config", {})
    mode = config.get("execution_mode", ExecutionMode.LOCAL)
    timeout = config.get("execution_timeout", 60)

    executor = ExecutorFactory.create(mode)
    result = executor.execute(state["script"], timeout)

    state["stdout"] = result.stdout
    state["stderr"] = result.stderr
    state["exit_code"] = result.exit_code
    state["timed_out"] = result.timed_out

    return state
