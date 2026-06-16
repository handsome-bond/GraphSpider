"""
AutonomousScraperGraph — LangGraph-based ReAct loop.

  GENERATE → EXECUTE → EVALUATE → REFLECT & FIX → GENERATE (retry)
                                  ↘ SUCCESS → END
"""

from langgraph.graph import StateGraph, END

from .state.autonomous_state import AutonomousState
from .execute_node import execute_node
from .evaluate_node import evaluate_node
from .reflect_and_fix_node import reflect_and_fix_node


def _generate_node(state: AutonomousState) -> AutonomousState:
    """
    Generate the initial scraper script using ScriptCreatorMultiGraph.
    On subsequent rounds (retry > 0), the script has already been updated
    by reflect_and_fix_node, so this is a no-op pass-through.
    """
    if state.get("retry_count", 0) == 0:
        from ..graphs.script_creator_multi_graph import ScriptCreatorMultiGraph

        graph = ScriptCreatorMultiGraph(
            prompt=state["prompt"],
            source=state["source"],
            config=state.get("config", {}),
        )
        state["script"] = graph.run()
        state["script_history"] = [state["script"]]
    # retry > 0: script already fixed by reflect node — just pass through
    return state


def _route_after_evaluate(state: AutonomousState) -> str:
    """LangGraph routing function."""
    return state.get("next", "reflect_and_fix")


def build_autonomous_graph() -> StateGraph:
    """Build and compile the ReAct agent graph."""
    workflow = StateGraph(AutonomousState)

    workflow.add_node("generate", _generate_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("reflect_and_fix", reflect_and_fix_node)

    workflow.set_entry_point("generate")

    workflow.add_edge("generate", "execute")
    workflow.add_edge("execute", "evaluate")

    workflow.add_conditional_edges(
        "evaluate",
        _route_after_evaluate,
        {
            "reflect_and_fix": "reflect_and_fix",
            "END": END,
        },
    )

    workflow.add_edge("reflect_and_fix", "generate")

    return workflow.compile()
