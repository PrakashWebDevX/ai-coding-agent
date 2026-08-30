"""Agent 2: Planner — analyzes the algorithm strategy before code is written."""
from backend.schemas.models import AgentState, PlanSchema, WorkflowStatus
from backend.services.llm_service import get_llm_service
from backend.utils.logger import get_logger, log_agent

logger = get_logger("planner_agent")

SYSTEM_PROMPT = """You are an expert algorithm planner for competitive programming.
Given a problem statement, respond ONLY with a JSON object with these exact keys:
data_structures (list of strings), algorithm_strategy (string), time_complexity (string),
space_complexity (string), edge_cases (list of strings), reasoning (string, 2-4 sentences).
No markdown, no prose outside the JSON."""


async def planner_node(state: AgentState) -> AgentState:
    log_agent(logger, "Planner", "Analyzing algorithm strategy")
    problem = state.problem
    if problem is None:
        raise ValueError("Planner requires a parsed problem in state")

    user_prompt = f"""Problem: {problem.title}
Difficulty: {problem.difficulty}
Description: {problem.description}
Examples: {[e.model_dump() for e in problem.examples]}
Constraints: {[c.text for c in problem.constraints]}
Function signature: {problem.function_signature}"""

    llm = get_llm_service()
    result = await llm.complete_json(SYSTEM_PROMPT, user_prompt)

    state.plan = PlanSchema(**result)
    state.status = WorkflowStatus.GENERATING_CODE
    state.logs.append(f"Plan generated: {state.plan.algorithm_strategy}")
    return state
