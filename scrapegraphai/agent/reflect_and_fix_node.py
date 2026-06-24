"""
Reflect & Fix node — intelligent failure diagnosis and repair.

Uses SmartDiagnosis to:
1. Extract ALL CSS selectors from the generated script
2. Compare against selectors that actually exist in the page HTML
3. Tell the LLM EXACTLY which selectors are hallucinated and which to use
4. Track cross-round memory to prevent repeating mistakes
"""

from .error_classifier import ErrorClassifier
from .smart_reflector import diagnose_failure
from .state.autonomous_state import AutonomousState


def reflect_and_fix_node(state: AutonomousState) -> AutonomousState:
    error_type = state.get("error_type", "UNKNOWN")

    # ── Build smart diagnosis ──────────────────────────────────
    diagnosis = diagnose_failure(
        script=state.get("script", ""),
        stderr=state.get("stderr", ""),
        stdout=state.get("stdout", ""),
        error_type=error_type,
        html_context=state.get("last_html", ""),
        round_history=state.get("round_history"),
    )

    diagnostic_context = diagnosis.to_prompt_context()

    # ── Simple sanitize for trivial errors ─────────────────────
    if ErrorClassifier.can_sanitize(
        ErrorClassifier.classify(state.get("stderr", ""), state.get("stdout", ""))
    ):
        state["fix_strategy"] = "sanitize"
        state["script_history"].append(state["script"])
        fixed = _apply_sanitizers(state["script"], state.get("source", ""))
        if fixed != state["script"]:
            state["script"] = fixed
        state["retry_count"] = state.get("retry_count", 0) + 1
        _record_round(state, "sanitize", diagnostic_context)
        return state

    # ── Smart regenerate — full pipeline with diagnosis ─────────
    state["fix_strategy"] = "regenerate"
    state["script_history"].append(state["script"])

    config = state.get("config", {})
    llm_config = config.get("llm", {})

    if not llm_config:
        state["retry_count"] = state.get("retry_count", 0) + 1
        _record_round(state, "skipped (no LLM config)", diagnostic_context)
        return state

    try:
        from ..graphs.script_creator_multi_graph import ScriptCreatorMultiGraph

        # The enriched prompt now contains:
        # 1. Original user request
        # 2. Full SmartDiagnosis: hallucinated selectors, available selectors,
        #    pagination type, previous round failures
        enriched_prompt = (
            f"{state['prompt']}\n\n"
            f"{diagnostic_context}"
        )

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
        state["failure_reason"] = f"Regenerate failed: {exc}"

    state["retry_count"] = state.get("retry_count", 0) + 1
    _record_round(state, "regenerate", diagnostic_context)
    return state


def _apply_sanitizers(script: str, source_url: str) -> str:
    """Re-run the safe sanitizer pipeline."""
    try:
        from ..nodes.generate_scraper_node import GenerateScraperNode, correct_urls_in_code
        dummy = GenerateScraperNode(
            input="x", output=["y"],
            library="playwright",
            website=source_url,
            node_config={"llm_model": None, "model_token": 128000},
        )
        return dummy._sanitize_script(script, source_url)
    except Exception:
        from ..nodes.generate_scraper_node import correct_urls_in_code
        return correct_urls_in_code(script, source_url)


def _record_round(state: AutonomousState, action: str, context: str = ""):
    """Append a round entry to the history."""
    history = list(state.get("round_history", []))
    rn = state.get("retry_count", 0)
    if any(r.get("round") == rn for r in history):
        return
    history.append({
        "round": rn,
        "error_type": state.get("error_type", ""),
        "fix_strategy": state.get("fix_strategy", ""),
        "action": action,
        "hallucinated_selectors": _extract_hallucinated(context),
    })
    state["round_history"] = history


def _extract_hallucinated(context: str) -> list:
    """Extract hallucinated selector names from diagnostic context."""
    import re
    return re.findall(r"❌\s+(\S+)\s+—", context)
