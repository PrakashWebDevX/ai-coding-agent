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
        "sql": ("select", "with", "insert", "update", "delete", "create"),
    }
    markers = code_start_markers.get(language, ("def ", "class ", "function "))
    case_insensitive = language == "sql"

    start_idx = 0
    for i, line in enumerate(lines):
        stripped_line = line.strip().lower() if case_insensitive else line.strip()
        if any(stripped_line.startswith(m) for m in markers):
            start_idx = i
            break
    return "\n".join(lines[start_idx:]).strip()


def _fix_escaped_newlines(code: str) -> str:
    """Some LLMs double-escape newlines inside their JSON response, so the parsed
    string ends up containing the literal two characters '\\' + 'n' instead of an
    actual line break. Detect that pattern (no real newlines present, but literal
    \\n sequences are) and unescape it.
    """
    if "\n" not in code and "\\n" in code:
        code = code.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
    return code


_KNOWN_HARNESS_CLASSES = ("ListNode", "TreeNode", "Node")
_PY_CLASS_BLOCK = re.compile(
    r"^class\s+({names})\b.*?(?=^class\s|^def\s|\Z)".format(
        names="|".join(_KNOWN_HARNESS_CLASSES)
    ),
    re.DOTALL | re.MULTILINE,
)


def _strip_redundant_helper_classes(code: str, starter_code: str | None) -> str:
    """If the starter code already provides a helper class (ListNode/TreeNode/Node)
    and the generated solution redefines it too, remove the redundant redefinition.
    A second, differently-scoped copy of these classes causes judge-side
    serialization failures even when the algorithm itself is correct."""
    if not starter_code:
        return code
    redundant = [name for name in _KNOWN_HARNESS_CLASSES if name in starter_code]
    if not redundant:
        return code

    def _strip_match(match: "re.Match[str]") -> str:
        return "" if match.group(1) in redundant else match.group(0)

    stripped = _PY_CLASS_BLOCK.sub(_strip_match, code)
    return stripped.strip()


async def code_formatter_node(state: AgentState) -> AgentState:
    log_agent(logger, "CodeFormatter", "Cleaning generated code")
    solution = state.solution
    if solution is None:
        raise ValueError("CodeFormatter requires a generated solution in state")

    cleaned = _fix_escaped_newlines(solution.code)
    cleaned = _strip_markdown_fences(cleaned)
    cleaned = _clean_leading_prose(cleaned, solution.language.value)
    starter_code = state.problem.starter_code if state.problem else None
    cleaned = _strip_redundant_helper_classes(cleaned, starter_code)

    state.formatted_code = cleaned
    state.logs.append("Code formatted and cleaned")
    return state
