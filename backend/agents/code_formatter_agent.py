"""Agent 4: Code Formatter — strips markdown/prose so only executable code remains."""
import re

from backend.schemas.models import AgentState
from backend.utils.logger import get_logger, log_agent

logger = get_logger("code_formatter_agent")

_FENCE_PATTERN = re.compile(r"```(?:\w+)?\n?(.*?)```", re.DOTALL)


def _strip_markdown_fences(code: str) -> str:
    match = _FENCE_PATTERN.search(code)
    if match:
        return match.group(1).strip()
    return code.strip()


def _clean_leading_prose(code: str, language: str) -> str:
    """Remove any leading explanatory lines that aren't actual code."""
    lines = code.splitlines()
    code_start_markers = {
        "python": ("def ", "class ", "import ", "from "),
        "java": ("class ", "public ", "import "),
        "cpp": ("#include", "class ", "int ", "void ", "using "),
        "javascript": ("function ", "const ", "let ", "var ", "class "),
    }
    markers = code_start_markers.get(language, ("def ", "class ", "function "))

    start_idx = 0
    for i, line in enumerate(lines):
        if any(line.strip().startswith(m) for m in markers):
            start_idx = i
            break
    return "\n".join(lines[start_idx:]).strip()


async def code_formatter_node(state: AgentState) -> AgentState:
    log_agent(logger, "CodeFormatter", "Cleaning generated code")
    solution = state.solution
    if solution is None:
        raise ValueError("CodeFormatter requires a generated solution in state")

    cleaned = _strip_markdown_fences(solution.code)
    cleaned = _clean_leading_prose(cleaned, solution.language.value)

    state.formatted_code = cleaned
    state.logs.append("Code formatted and cleaned")
    return state
