"""Agent 9: Session Memory — persists problem, attempts, errors, and final solution to SQLite."""
from backend.memory import repository
from backend.schemas.models import AgentState, WorkflowStatus
from backend.utils.logger import get_logger, log_agent

logger = get_logger("session_memory_agent")


async def session_memory_node(state: AgentState) -> AgentState:
    log_agent(logger, "SessionMemory", "Persisting session state")

    await repository.upsert_session(state)

    if state.problem:
        await repository.save_problem(state)
    if state.formatted_code:
        await repository.save_attempt(state)
    if state.error:
        await repository.save_error(state)
    if state.status == WorkflowStatus.SUCCESS and state.solution:
        await repository.save_final_solution(state)

    for entry in state.logs[-5:]:
        await repository.add_log(state.session_id, state.status.value, entry)

    return state
