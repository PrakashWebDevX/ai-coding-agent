"""Agent: Language Selector — ensures the site's editor language dropdown matches
state.language before code is pasted. Runs after code generation/formatting and
before the browser editor paste step, since changing the language often resets
the editor's contents."""
from backend.browser.playwright_manager import BrowserManager
from backend.schemas.models import AgentState
from backend.utils.logger import get_logger, log_agent

logger = get_logger("language_selector_agent")


async def language_selector_node(state: AgentState) -> AgentState:
    log_agent(logger, "LanguageSelector", f"Ensuring editor language is set to {state.language.value}")
    browser = BrowserManager()
    try:
        await browser.connect()
        matched = await browser.select_language(state.language.value)
        if not matched:
            state.logs.append(
                f"Could not confirm language dropdown matches '{state.language.value}'; "
                "proceeding with whatever is currently selected"
            )
        else:
            state.logs.append(f"Editor language set to {state.language.value}")
    finally:
        await browser.disconnect()
    return state
