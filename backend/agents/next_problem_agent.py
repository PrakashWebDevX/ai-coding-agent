"""Agent: Next Problem — advances the browser to the next problem, either by
navigating to an explicit URL from a queue, or by clicking the site's own
'next problem' control when no explicit queue is given."""
from backend.browser.playwright_manager import BrowserManager
from backend.utils.logger import get_logger, log_agent

logger = get_logger("next_problem_agent")


async def go_to_next_problem(next_url: str | None) -> bool:
    """Returns True if navigation succeeded (either via explicit URL or site control)."""
    log_agent(logger, "NextProblem", f"Advancing to next problem ({next_url or 'via site nav'})")
    browser = BrowserManager()
    try:
        await browser.connect()
        if next_url:
            await browser.navigate_to(next_url)
            return True
        return await browser.click_next_problem()
    finally:
        await browser.disconnect()
