"""
AgentLoop — the main user-facing class for GraphSpider Agent.

Usage:
    from scrapegraphai.agent import AgentLoop

    agent = AgentLoop(
        prompt="Extract dataset results...",
        source="https://example.com/data",
        config={"llm": {...}, "output_file": "...", "max_items": 50},
    )
    result = agent.run()

    result.success    # bool
    result.script     # final generated script
    result.data       # scraped data (if successful)
    result.history    # per-round diagnostics
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .state.autonomous_state import AutonomousState


@dataclass
class AgentResult:
    """Structured result from an AgentLoop run."""
    success: bool
    script: str
    data: Optional[str] = None
    total_rounds: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


class AgentLoop:
    """
    Autonomous web scraper agent with self-healing ReAct loop.

    Generate → Execute → Evaluate → Reflect & Fix → Retry (max 3 rounds).

    Parameters
    ----------
    prompt : str
        What to extract (e.g. "Extract dataset results. Fields: title, date.")
    source : str
        Target URL to scrape.
    config : dict
        LLM config, output settings, and agent hyper-parameters:
        - max_rounds (int): max retries, default 3
        - execution_timeout (int): seconds per run, default 60
        - output_file / output_format / max_items: passed through to
          ScriptCreatorMultiGraph
    """

    def __init__(self, prompt: str, source: str, config: dict):
        self.prompt = prompt
        self.source = source
        self.config = config

        self.max_rounds = config.get("max_rounds", 3)

    def run(self) -> AgentResult:
        """Execute the autonomous agent loop and return results."""
        from .autonomous_graph import build_autonomous_graph

        graph = build_autonomous_graph()

        initial_state: AutonomousState = {
            "prompt": self.prompt,
            "source": self.source,
            "config": self.config,
            "script": "",
            "script_history": [],
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "timed_out": False,
            "is_success": False,
            "error_type": "",
            "error_summary": "",
            "failure_reason": "",
            "retry_count": 0,
            "max_rounds": self.max_rounds,
            "fix_strategy": "",
            "round_history": [],
            "next": "",
        }

        try:
            final_state = graph.invoke(initial_state)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            # Log the full traceback for debugging
            if self.config.get("verbose"):
                print(f"\n[AgentLoop] Error during execution:\n{tb}")
            return AgentResult(
                success=False,
                script=initial_state.get("script", ""),
                total_rounds=initial_state.get("retry_count", 0),
                history=initial_state.get("round_history", []),
                error=f"{exc}\n\n{tb[-500:]}",  # last 500 chars of traceback
            )

        return AgentResult(
            success=final_state.get("is_success", False),
            script=final_state.get("script", ""),
            data=final_state.get("stdout", ""),
            total_rounds=final_state.get("retry_count", 0),
            history=final_state.get("round_history", []),
            error=final_state.get("failure_reason"),
        )
