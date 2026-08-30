"""Agent 5: Browser Editor — pastes formatted code into the Monaco editor, replacing it entirely."""
from backend.browser.playwright_manager import BrowserManager
from backend.schemas.models import AgentState, WorkflowStatus
from backend.utils.logger import get_logger, log_agent

logger = get_logger("browser_editor_agent")


async def browser_editor_node(state: AgentState) -> AgentState:
    log_agent(logger, "BrowserEditor", "Pasting solution into editor")
    if not state.formatted_code:
        raise ValueError("BrowserEditor requires formatted_code in state")

    browser = BrowserManager()
    try:
        await browser.connect()
        await browser.replace_editor_code(state.formatted_code)
    finally:
        await browser.disconnect()

    state.status = WorkflowStatus.AWAITING_USER_RUN
    state.logs.append("Code pasted into editor. Awaiting user to trigger Run.")
    return state
