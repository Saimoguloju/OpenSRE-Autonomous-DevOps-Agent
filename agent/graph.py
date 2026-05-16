import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from agent.state import IncidentState
from agent.nodes import analyze_root_cause, decide_action, execute_action, mark_ignored

logger = logging.getLogger(__name__)


def _route_after_decide(state: IncidentState) -> Literal["execute_action", "await_human", END]:
    if state["status"] == "acting":
        return "execute_action"
    if state["status"] == "awaiting_approval":
        return "await_human"
    return END


def _route_after_human(state: IncidentState) -> Literal["execute_action", "mark_ignored", END]:
    if state.get("human_approved") is True:
        return "execute_action"
    if state.get("human_approved") is False:
        return "mark_ignored"
    # Still waiting — stay in place (graph will be re-invoked externally)
    return END


def _await_human(state: IncidentState) -> IncidentState:
    """Placeholder node — real approval comes via Slack callback updating the DB."""
    logger.info("Incident %s awaiting human approval via Slack.", state["incident_id"])
    return state


def build_graph() -> StateGraph:
    graph = StateGraph(IncidentState)

    graph.add_node("analyze_root_cause", analyze_root_cause)
    graph.add_node("decide_action", decide_action)
    graph.add_node("await_human", _await_human)
    graph.add_node("execute_action", execute_action)
    graph.add_node("mark_ignored", mark_ignored)

    graph.set_entry_point("analyze_root_cause")
    graph.add_edge("analyze_root_cause", "decide_action")
    graph.add_conditional_edges("decide_action", _route_after_decide, {
        "execute_action": "execute_action",
        "await_human": "await_human",
        END: END,
    })
    graph.add_conditional_edges("await_human", _route_after_human, {
        "execute_action": "execute_action",
        "mark_ignored": "mark_ignored",
        END: END,
    })
    graph.add_edge("execute_action", END)
    graph.add_edge("mark_ignored", END)

    return graph.compile()


# Singleton compiled graph
sre_graph = build_graph()
