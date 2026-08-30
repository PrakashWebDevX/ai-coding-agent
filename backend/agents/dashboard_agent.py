"""Agent 10: Dashboard — summarizes current run state for the Streamlit UI to poll."""
from backend.schemas.models import AgentState, WorkflowStatus
from backend.utils.logger import get_logger, log_agent

logger = get_logger("dashboard_agent")


async def dashboard_update_node(state: AgentState) -> AgentState:
    log_agent(logger, "Dashboard", f"Status: {state.status.value} | Retries: {state.retry_count}")

    if state.status == WorkflowStatus.SUCCESS:
        state.logs.append("✅ ALL TESTS PASSED — please review the solution and submit manually.")
    elif state.status == WorkflowStatus.FAILED_MAX_RETRIES:
        state.logs.append("⚠️ Max retries reached without a passing solution. Manual intervention needed.")

    return state
