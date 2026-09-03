"""
LangGraph orchestration.

Two solve graphs are provided:

1. solve_graph — Problem -> Plan -> Generate -> Format -> SelectLanguage -> Paste ->
   [STOP, awaiting user]. Used by the interactive dashboard flow, where the user
   reviews the pasted code and clicks "Run Tests" themselves.

2. autonomous_solve_graph — the same pipeline, but continues straight into
   Run -> Analyze -> Retry (looping internally) -> Success/MaxRetries, with no
   pause for a human click. Used by batch/loop mode. In both graphs, submission
   is never automated — there is no click_submit anywhere in this codebase.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.agents.browser_editor_agent import browser_editor_node
from backend.agents.code_formatter_agent import code_formatter_node
from backend.agents.code_generator_agent import code_generator_node
from backend.agents.dashboard_agent import dashboard_update_node
from backend.agents.error_analyzer_agent import error_analyzer_node
from backend.agents.language_selector_agent import language_selector_node
from backend.agents.planner_agent import planner_node
from backend.agents.problem_reader_agent import problem_reader_node
from backend.agents.retry_agent import retry_node
from backend.agents.session_memory_agent import session_memory_node
from backend.agents.submit_agent import submit_node
from backend.agents.test_runner_agent import test_runner_node
from backend.schemas.models import AgentState, WorkflowStatus


def _route_after_error_analysis(state: AgentState) -> str:
    if state.success:
        return "success"
    if state.retry_count >= state.max_retries:
        return "max_retries"
    return "retry"


def build_solve_graph():
    """Graph 1: Problem -> Plan -> Generate -> Format -> SelectLanguage -> Paste.
    Stops for user to click Run."""
    graph = StateGraph(AgentState)

    graph.add_node("problem_reader", problem_reader_node)
    graph.add_node("planner", planner_node)
    graph.add_node("generator", code_generator_node)
    graph.add_node("formatter", code_formatter_node)
    graph.add_node("language_selector", language_selector_node)
    graph.add_node("paste_editor", browser_editor_node)
    graph.add_node("memory", session_memory_node)
    graph.add_node("dashboard", dashboard_update_node)

    graph.set_entry_point("problem_reader")
    graph.add_edge("problem_reader", "planner")
    graph.add_edge("planner", "generator")
    graph.add_edge("generator", "formatter")
    graph.add_edge("formatter", "language_selector")
    graph.add_edge("language_selector", "paste_editor")
    graph.add_edge("paste_editor", "memory")
    graph.add_edge("memory", "dashboard")
    graph.add_edge("dashboard", END)

    return graph.compile()


def build_test_and_retry_graph():
    """Graph 2: RunTest -> Analyze -> (Retry loop back through Generate/Format/Paste) | Success.
    Used by the interactive dashboard's "Run Tests" button — stops after each re-paste for
    the user to click Run again."""
    graph = StateGraph(AgentState)

    graph.add_node("run_test", test_runner_node)
    graph.add_node("analyze_error", error_analyzer_node)
    graph.add_node("retry", retry_node)
    graph.add_node("formatter", code_formatter_node)
    graph.add_node("paste_editor", browser_editor_node)
    graph.add_node("memory", session_memory_node)
    graph.add_node("dashboard", dashboard_update_node)

    graph.set_entry_point("run_test")
    graph.add_edge("run_test", "analyze_error")

    graph.add_conditional_edges(
        "analyze_error",
        _route_after_error_analysis,
        {
            "success": "memory",
            "retry": "retry",
            "max_retries": "memory",
        },
    )

    graph.add_edge("formatter", "paste_editor")
    graph.add_edge("paste_editor", "memory")  # after re-pasting, log and stop; user clicks Run again
    graph.add_edge("memory", "dashboard")
    graph.add_edge("dashboard", END)

    return graph.compile()


def build_autonomous_solve_graph():
    """Full autonomous pipeline for batch/loop mode: reads the problem, solves it,
    runs tests, self-corrects via the retry loop, and — on success — submits it,
    with NO pause for human input at any point. This is the opt-in fully-autonomous
    mode; the interactive dashboard flow (solve_graph / test_and_retry_graph) never
    submits and always stops for manual review.
    """
    graph = StateGraph(AgentState)

    graph.add_node("problem_reader", problem_reader_node)
    graph.add_node("planner", planner_node)
    graph.add_node("generator", code_generator_node)
    graph.add_node("formatter", code_formatter_node)
    graph.add_node("language_selector", language_selector_node)
    graph.add_node("paste_editor", browser_editor_node)
    graph.add_node("run_test", test_runner_node)
    graph.add_node("analyze_error", error_analyzer_node)
    graph.add_node("retry", retry_node)
    graph.add_node("submit", submit_node)
    graph.add_node("memory", session_memory_node)
    graph.add_node("dashboard", dashboard_update_node)

    graph.set_entry_point("problem_reader")
    graph.add_edge("problem_reader", "planner")
    graph.add_edge("planner", "generator")
    graph.add_edge("generator", "formatter")
    graph.add_edge("formatter", "language_selector")
    graph.add_edge("language_selector", "paste_editor")
    graph.add_edge("paste_editor", "run_test")
    graph.add_edge("run_test", "analyze_error")

    graph.add_conditional_edges(
        "analyze_error",
        _route_after_error_analysis,
        {
            "success": "submit",
            "retry": "retry",
            "max_retries": "memory",
        },
    )

    # Autonomous retry loop: no stop, straight back through the same
    # format -> select-language (no-op if already correct) -> paste -> run path
    # used on the first pass. (Do NOT add a second edge out of "formatter" here —
    # a node with two outgoing edges runs both targets in parallel in LangGraph,
    # which caused concurrent writes to the same state and an InvalidUpdateError.)
    graph.add_edge("retry", "formatter")

    graph.add_edge("submit", "memory")
    graph.add_edge("memory", "dashboard")
    graph.add_edge("dashboard", END)

    return graph.compile()


# Compiled singletons reused across requests.
solve_graph = build_solve_graph()
test_and_retry_graph = build_test_and_retry_graph()
autonomous_solve_graph = build_autonomous_solve_graph()


async def run_solve_workflow(session_id: str, language: str, max_retries: int) -> AgentState:
    initial_state = AgentState(
        session_id=session_id,
        language=language,
        max_retries=max_retries,
        status=WorkflowStatus.READING_PROBLEM,
    )
    result = await solve_graph.ainvoke(initial_state)
    return AgentState(**result)


async def run_test_workflow(state: AgentState) -> AgentState:
    state.status = WorkflowStatus.RUNNING_TESTS
    result = await test_and_retry_graph.ainvoke(state)
    return AgentState(**result)


async def run_autonomous_workflow(session_id: str, language: str, max_retries: int) -> AgentState:
    """Runs the full autonomous pipeline for whatever problem is currently open in
    the browser tab: read -> plan -> generate -> paste -> run -> retry-loop, with
    no pause for human input, ending in success or max-retries."""
    initial_state = AgentState(
        session_id=session_id,
        language=language,
        max_retries=max_retries,
        status=WorkflowStatus.READING_PROBLEM,
    )
    # Recursion limit: formatter/paste/run/analyze/retry can cycle up to max_retries+1
    # times, each cycle touching ~5 nodes, plus the initial ~7-node run-up. Pad generously.
    config = {"recursion_limit": max(50, (max_retries + 2) * 10)}
    result = await autonomous_solve_graph.ainvoke(initial_state, config=config)
    return AgentState(**result)
