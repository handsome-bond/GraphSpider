"""
AutonomousState — shared state dict for the LangGraph agent loop.

Carries the script, execution output, error diagnosis, and retry
counters across Generate → Execute → Evaluate → Reflect & Fix nodes.
"""

from typing import TypedDict, List, Optional, Any


class AutonomousState(TypedDict, total=False):
    # ── Input ──
    prompt: str
    source: str
    config: dict

    # ── Current script ──
    script: str
    script_history: List[str]

    # ── Execution result ──
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool

    # ── Evaluation ──
    is_success: bool
    error_type: str
    error_summary: str
    failure_reason: str

    # ── Control ──
    retry_count: int
    max_rounds: int
    fix_strategy: str
    round_history: List[dict]

    # ── LangGraph internal ──
    next: str  # routing decision: "reflect_and_fix" | "END"
