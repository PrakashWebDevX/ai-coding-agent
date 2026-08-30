"""Agent 6: Test Runner — clicks Run (never Submit) and waits for execution to complete."""
from backend.browser.playwright_manager import BrowserManager
from backend.schemas.models import AgentState, WorkflowStatus
from backend.utils.logger import get_logger, log_agent

logger = get_logger("test_runner_agent")


async def test_runner_node(state: AgentState) -> AgentState:
    log_agent(logger, "TestRunner", "Running tests")
    browser = BrowserManager()
    try:
        await browser.connect()
        await browser.click_run()
        await browser.wait_for_run_completion()
        result = await browser.read_result()
    finally:
        await browser.disconnect()

    combined = "\n".join(filter(None, [
        result.get("result_text"),
        result.get("error_text"),
        result.get("failed_cases_text"),
        result.get("console_text"),
    ]))

    state.test_result_raw = combined
    state.status = WorkflowStatus.ANALYZING_ERROR
    state.logs.append("Test run completed; reading results")
    return state
