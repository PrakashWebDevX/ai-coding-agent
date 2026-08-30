"""Agent 7: Error Analyzer — classifies raw execution output into structured error data."""
import re

from backend.schemas.models import AgentState, ErrorSchema, ErrorType, FailedTestCase, WorkflowStatus
from backend.utils.logger import get_logger, log_agent

logger = get_logger("error_analyzer_agent")

_SUCCESS_MARKERS = ("accepted", "all tests passed", "success", "passed")
_ERROR_PATTERNS: list[tuple[ErrorType, list[str]]] = [
    (ErrorType.COMPILER_ERROR, ["compile error", "syntaxerror", "compilation error"]),
    (ErrorType.TIME_LIMIT_EXCEEDED, ["time limit exceeded", "tle"]),
    (ErrorType.MEMORY_LIMIT_EXCEEDED, ["memory limit exceeded", "mle"]),
    (ErrorType.RUNTIME_ERROR, ["runtime error", "traceback", "exception", "segmentation fault"]),
    (ErrorType.WRONG_ANSWER, ["wrong answer", "output differs", "expected", "mismatch"]),
]


def _classify(raw: str) -> ErrorType:
    lowered = raw.lower()
    for error_type, keywords in _ERROR_PATTERNS:
        if any(k in lowered for k in keywords):
            return error_type
    return ErrorType.UNKNOWN


def _extract_failed_cases(raw: str) -> list[FailedTestCase]:
    cases = []
    # Best-effort pattern: "Input: ... Expected: ... Actual/Output: ..."
    pattern = re.compile(
        r"Input:?\s*(.+?)\s*Expected(?: Output)?:?\s*(.+?)\s*(?:Actual|Output|Got):?\s*(.+?)(?=Input:|$)",
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(raw):
        cases.append(
            FailedTestCase(
                input=match.group(1).strip(),
                expected_output=match.group(2).strip(),
                actual_output=match.group(3).strip(),
            )
        )
    return cases


async def error_analyzer_node(state: AgentState) -> AgentState:
    log_agent(logger, "ErrorAnalyzer", "Classifying test results")
    raw = state.test_result_raw or ""

    if any(marker in raw.lower() for marker in _SUCCESS_MARKERS) and not any(
        kw in raw.lower() for _, kws in _ERROR_PATTERNS for kw in kws
    ):
        state.success = True
        state.status = WorkflowStatus.SUCCESS
        state.error = None
        state.logs.append("All tests passed")
        return state

    error_type = _classify(raw)
    failed_cases = _extract_failed_cases(raw)

    state.error = ErrorSchema(error_type=error_type, raw_message=raw, failed_test_cases=failed_cases)
    state.success = False
    state.status = WorkflowStatus.RETRYING
    state.logs.append(f"Detected error: {error_type.value}")
    return state
