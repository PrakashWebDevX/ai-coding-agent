"""Agent 3: Code Generator — writes the solution following the exact function signature."""
from backend.schemas.models import AgentState, GeneratedSolutionSchema, WorkflowStatus
from backend.services.llm_service import get_llm_service
from backend.utils.logger import get_logger, log_agent

logger = get_logger("code_generator_agent")

SYSTEM_PROMPT = """You are an expert software engineer. Generate a complete, correct, efficient
solution to the given coding problem in the requested language. You MUST follow the given
function signature exactly if one is provided.

CRITICAL: If the starter code already defines a helper class (e.g. ListNode, TreeNode, Node),
do NOT redefine that class in your solution. The judge's test harness provides its own copy of
that exact class and will construct its inputs using it — if your code defines a second,
different version of the same class name, objects you return will be considered a different
type than the harness expects and will fail to serialize, even if your algorithm is correct.
Only implement the requested method body, assuming any such helper classes already exist
exactly as given in the starter code.

Respond ONLY with a JSON object with keys:
code (string, the complete solution with any necessary imports) and explanation
(string, 2-4 sentences on the approach). No markdown fences inside the code field's surrounding
JSON — the code field itself may contain newlines but must be valid JSON string content."""


async def code_generator_node(state: AgentState) -> AgentState:
    log_agent(logger, "CodeGenerator", f"Generating {state.language.value} solution")
    problem = state.problem
    plan = state.plan
    if problem is None or plan is None:
        raise ValueError("CodeGenerator requires problem and plan in state")

    user_prompt = f"""Language: {state.language.value}
Problem: {problem.title}
Description: {problem.description}
Function signature to follow exactly: {problem.function_signature}
Starter code: {problem.starter_code}
Algorithm plan: {plan.algorithm_strategy}
Edge cases to handle: {plan.edge_cases}
Time complexity target: {plan.time_complexity}"""

    llm = get_llm_service()
    result = await llm.complete_json(SYSTEM_PROMPT, user_prompt, temperature=0.15)

    state.solution = GeneratedSolutionSchema(
        code=result["code"],
        language=state.language,
        explanation=result.get("explanation", ""),
        plan=plan,
        attempt_number=state.retry_count + 1,
    )
    state.status = WorkflowStatus.PASTING_CODE
    state.logs.append("Code generated")
    return state
