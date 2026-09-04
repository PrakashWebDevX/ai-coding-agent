"""Agent 8: Retry — builds a fix prompt from the original problem, previous code, and the error."""
from backend.schemas.models import AgentState, GeneratedSolutionSchema, Language, WorkflowStatus
from backend.services.llm_service import get_llm_service
from backend.utils.logger import get_logger, log_agent, log_retry

logger = get_logger("retry_agent")

SYSTEM_PROMPT = """You are an expert debugger. You will be given a coding problem, the previous
incorrect solution, and the error it produced. Make the MINIMAL necessary change to fix the bug —
do not rewrite the solution from scratch unless absolutely required.

CRITICAL: If the error mentions a type/serialization mismatch involving a class like ListNode,
TreeNode, or Node, the cause is almost always that the previous code redefined that class
instead of using the one the judge's harness already provides. In that case, remove the
redundant class definition entirely rather than trying to fix its fields.

Respond ONLY with a JSON
object with keys: code (the corrected complete solution) and explanation (what was wrong and
what you changed, 2-3 sentences)."""

SQL_SYSTEM_PROMPT = """You are an expert database engineer debugging a SQL query. You will be
given a SQL problem, the previous incorrect query, and the error it produced. The judge's editor
accepts ONLY a raw SQL query — no function wrapper, no Python, no class. Make the MINIMAL
necessary change to fix the bug. If the previous "solution" was Python code (e.g. a def that
returns a string), that is itself the bug: rewrite it as a raw SQL statement with no wrapper
of any kind.

Respond ONLY with a JSON object with keys: code (the corrected raw SQL query, ending with a
semicolon) and explanation (what was wrong and what you changed, 2-3 sentences)."""


def _build_retry_prompt(state: AgentState) -> str:
    problem = state.problem
    error = state.error
    failed_cases_text = "\n".join(
        f"Input: {c.input}\nExpected: {c.expected_output}\nActual: {c.actual_output}"
        for c in (error.failed_test_cases if error else [])
    )
    return f"""Original problem: {problem.title}
Description: {problem.description}
Constraints: {[c.text for c in problem.constraints]}

Previous code:
{state.formatted_code}

Error type: {error.error_type.value if error else 'unknown'}
Error message: {error.raw_message if error else ''}
Failed test cases:
{failed_cases_text or 'none captured'}
"""


async def retry_node(state: AgentState) -> AgentState:
    state.retry_count += 1
    log_retry(logger, state.retry_count, "Building fix prompt from error context")

    if state.retry_count > state.max_retries:
        state.status = WorkflowStatus.FAILED_MAX_RETRIES
        state.logs.append(f"Max retries ({state.max_retries}) exceeded. Stopping.")
        return state

    prompt = _build_retry_prompt(state)
    system_prompt = SQL_SYSTEM_PROMPT if state.language == Language.SQL else SYSTEM_PROMPT
    llm = get_llm_service()
    result = await llm.complete_json(system_prompt, prompt, temperature=0.15)

    state.solution = GeneratedSolutionSchema(
        code=result["code"],
        language=state.language,
        explanation=result.get("explanation", ""),
        plan=state.plan,
        attempt_number=state.retry_count + 1,
    )
    state.status = WorkflowStatus.GENERATING_CODE
    log_agent(logger, "Retry", "New candidate solution generated; routing back through formatter")
    return state
