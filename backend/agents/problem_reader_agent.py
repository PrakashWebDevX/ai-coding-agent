"""Agent 1: Problem Reader — reads the active browser tab and extracts a structured problem."""
from backend.browser.dom_parser import DomParser
from backend.browser.playwright_manager import BrowserManager
from backend.schemas.models import AgentState, WorkflowStatus
from backend.utils.logger import get_logger, log_agent

logger = get_logger("problem_reader_agent")


async def problem_reader_node(state: AgentState) -> AgentState:
    log_agent(logger, "ProblemReader", "Reading current browser tab")
    browser = BrowserManager()
    try:
        await browser.connect()
        parser = DomParser(browser)
        problem = await parser.parse_current_problem()
        state.problem = problem
        state.url = problem.url
        state.status = WorkflowStatus.PLANNING
        state.logs.append(f"Extracted problem: {problem.title}")
    finally:
        await browser.disconnect()
    return state
