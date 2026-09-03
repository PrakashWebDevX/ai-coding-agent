"""Agent: Submit — clicks the site's Submit button after tests have passed.

Only wired into the autonomous batch-mode graph. The interactive dashboard flow
(solve_graph / test_and_retry_graph) never includes this node, so a normal
"Read & Solve Problem" + "Run Tests" session still stops for manual review, as
before. Auto-submit is opt-in, and only active when running Batch Mode.
"""
from backend.browser.playwright_manager import BrowserManager
from backend.schemas.models import AgentState
from backend.utils.logger import get_logger, log_agent

logger = get_logger("submit_agent")


async def submit_node(state: AgentState) -> AgentState:
    log_agent(logger, "Submit", "Tests passed — submitting solution")
    browser = BrowserManager()
    try:
        await browser.connect()
        await browser.click_submit()
        await browser.wait_for_submit_completion()
        result = await browser.read_result()
    finally:
        await browser.disconnect()

    submit_text = result.get("result_text") or ""
    state.logs.append(f"Submitted. Judge result: {submit_text[:200] or 'unknown'}")
    return state
