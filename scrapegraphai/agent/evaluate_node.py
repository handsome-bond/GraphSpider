"""
Evaluate node — quality-check the execution result and route accordingly.
"""

from .error_classifier import ErrorClassifier
from .state.autonomous_state import AutonomousState


def evaluate_node(state: AutonomousState) -> AutonomousState:
    """
    Classify the execution output.
    Sets state["is_success"] and state["next"] for LangGraph routing.
    """
    classification = ErrorClassifier.classify(
        state.get("stderr", ""),
        state.get("stdout", ""),
    )

    state["error_type"] = classification.error_type
    state["error_summary"] = classification.suggestion

    # ── Success check ──
    stderr = state.get("stderr", "")
    stdout = state.get("stdout", "")
    exit_code = state.get("exit_code", -1)

    if not stderr and stdout.strip() and exit_code == 0:
        stripped = stdout.strip()

        if stripped.startswith("[") and not stripped == "[]":
            # Count items — if suspiciously few, pagination may have failed
            try:
                import json
                data = json.loads(stripped)
                item_count = len(data) if isinstance(data, list) else 1
            except Exception:
                item_count = stripped.count('"title"')  # rough estimate

            max_items = state.get("config", {}).get("max_items", 50)
            if item_count < max(10, max_items // 2):
                # Too few items — likely only scraped page 1
                state["is_success"] = False
                state["error_type"] = "LOW_COUNT"
                state["error_summary"] = (
                    f"Only {item_count} items scraped (expected ~{max_items}). "
                    f"Pagination may have failed."
                )
            else:
                state["is_success"] = True
                state["next"] = "END"
                return state

        elif len(stripped) > 20 and not stripped == "[]":
            state["is_success"] = True
            state["next"] = "END"
            return state

    # ── Login wall detection ──
    # If stdout contains login/sign-in text, the site requires authentication.
    # Retrying won't help — tell the user to log in first.
    LOGIN_INDICATORS = [
        "login", "sign in", "signin", "请登录", "登录", "登入",
        "captcha", "验证码", "扫码", "qr code",
    ]
    combined_lower = (state.get("stdout", "") + " " + state.get("stderr", "")).lower()
    if any(ind in combined_lower for ind in LOGIN_INDICATORS):
        state["is_success"] = False
        state["error_type"] = "LOGIN_REQUIRED"
        state["error_summary"] = (
            "This site requires login. Set 'interactive_login': true in config "
            "to open a browser for manual login. Auth state will be saved for "
            "subsequent runs via storage_state."
        )
        state["next"] = "END"
        state["failure_reason"] = state["error_summary"]
        return state

    # ── Failure ──
    state["is_success"] = False
    retry = state.get("retry_count", 0)
    max_rounds = state.get("max_rounds", 3)

    if retry >= max_rounds:
        state["next"] = "END"
        state["failure_reason"] = f"Exceeded max rounds ({max_rounds})"
        return state

    state["next"] = "reflect_and_fix"
    return state
