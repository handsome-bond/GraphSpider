"""
Reflect & Fix node — diagnose failures and repair the scraper script.

Two-tier strategy:
  Tier 1 (sanitize):  fast regex-based fixes, no LLM call — for
                      NameError, IndentError, JS syntax, URL issues.
  Tier 2 (regenerate): LLM re-generates the script with error context
                      — for Timeout, 403, EmptyResult, Unknown.
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from .error_classifier import ErrorClassifier
from .reflect_prompts import TEMPLATE_ERROR_ANALYSIS
from .diff_applier import apply_llm_fix
from .state.autonomous_state import AutonomousState


def reflect_and_fix_node(state: AutonomousState) -> AutonomousState:
    error_type = state.get("error_type", "UNKNOWN")

    # ── Tier 1: sanitize (fast, no LLM) ──────────────────────────
    if ErrorClassifier.can_sanitize(
        ErrorClassifier.classify(state.get("stderr", ""), state.get("stdout", ""))
    ):
        state["fix_strategy"] = "sanitize"
        state["script_history"].append(state["script"])

        # Re-run the existing sanitizer pipeline on the broken script
        fixed = _apply_sanitizers(state["script"], state.get("source", ""))
        if fixed != state["script"]:
            state["script"] = fixed
        state["retry_count"] = state.get("retry_count", 0) + 1

        _record_round(state, "sanitize")
        return state

    # ── Tier 2: regenerate — re-run the FULL pipeline ─────────────
    # A bare LLM call has no HTML context, no CSS hints, no sanitizers.
    # Re-running ScriptCreatorMultiGraph with error context in the prompt
    # is the only way to get a properly-generated script.
    state["fix_strategy"] = "regenerate"
    state["script_history"].append(state["script"])

    config = state.get("config", {})
    llm_config = config.get("llm", {})

    if not llm_config:
        state["retry_count"] = state.get("retry_count", 0) + 1
        _record_round(state, "skipped (no LLM config)")
        return state

    try:
        from ..graphs.script_creator_multi_graph import ScriptCreatorMultiGraph

        # Inject the error into the prompt so the pipeline knows what
        # went wrong last time.
        error_context = (
            f"\n\n[PREVIOUS ATTEMPT FAILED]\n"
            f"Error type: {error_type}\n"
            f"Error detail: {state.get('error_summary', '')}\n"
            f"Stderr: {state.get('stderr', '')[:500]}\n"
            f"Fix this error in the new script.\n"
        )
        enriched_prompt = state["prompt"] + error_context

        # Disable interactive login during retries — we already have auth.
        retry_config = dict(config)
        retry_config["wait_for_user"] = False
        retry_config["verbose"] = False

        graph = ScriptCreatorMultiGraph(
            prompt=enriched_prompt,
            source=state["source"],
            config=retry_config,
        )
        new_script = graph.run()

        if new_script and not new_script.startswith("Failed"):
            state["script"] = new_script

    except Exception as exc:
        state["failure_reason"] = f"Regenerate via ScriptCreatorMultiGraph failed: {exc}"

    state["retry_count"] = state.get("retry_count", 0) + 1
    _record_round(state, "regenerate")
    return state


def _apply_sanitizers(script: str, source_url: str) -> str:
    """Re-run the existing GenerateScraperNode sanitizer pipeline."""
    try:
        from ..nodes.generate_scraper_node import GenerateScraperNode, correct_urls_in_code

        # Instantiate a dummy node to access its sanitizers
        dummy = GenerateScraperNode(
            input="x", output=["y"],
            library="playwright",
            website=source_url,
            node_config={
                "llm_model": None,
                "model_token": 128000,
            },
        )

        # Run the full sanitizer chain
        code = dummy._sanitize_script(script, source_url)
        return code
    except Exception:
        # Minimal fallback: at least fix URLs
        from ..nodes.generate_scraper_node import correct_urls_in_code
        return correct_urls_in_code(script, source_url)


def _build_llm(llm_config: dict):
    """Build an LLM instance from config dict (reuses AbstractGraph logic)."""
    from ..graphs.abstract_graph import AbstractGraph

    # Create a minimal graph instance just to use _create_llm
    class _TmpGraph(AbstractGraph):
        def _create_graph(self):
            pass
        def run(self):
            pass

    tmp = _TmpGraph.__new__(_TmpGraph)
    return tmp._create_llm(llm_config)


def _record_round(state: AutonomousState, action: str):
    """Append a round entry to the history. Avoid duplicates."""
    history = list(state.get("round_history", []))
    rn = state.get("retry_count", 0)

    # Skip if this round was already recorded
    if any(r.get("round") == rn for r in history):
        return

    history.append({
        "round": rn,
        "error_type": state.get("error_type", ""),
        "fix_strategy": state.get("fix_strategy", ""),
        "action": action,
    })
    state["round_history"] = history
