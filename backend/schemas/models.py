"""
Typed contracts for the entire system. Every agent reads/writes these models
so the LangGraph state is always structured and validated.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    PYTHON = "python"
    JAVA = "java"
    CPP = "cpp"
    JAVASCRIPT = "javascript"


class Difficulty(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"
    UNKNOWN = "Unknown"


class ErrorType(str, Enum):
    COMPILER_ERROR = "compiler_error"
    RUNTIME_ERROR = "runtime_error"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    UNKNOWN = "unknown"


class WorkflowStatus(str, Enum):
    IDLE = "idle"
    READING_PROBLEM = "reading_problem"
    PLANNING = "planning"
    GENERATING_CODE = "generating_code"
    PASTING_CODE = "pasting_code"
    AWAITING_USER_RUN = "awaiting_user_run"
    RUNNING_TESTS = "running_tests"
    ANALYZING_ERROR = "analyzing_error"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED_MAX_RETRIES = "failed_max_retries"
    ERROR = "error"


class ExampleSchema(BaseModel):
    input: str
    output: str
    explanation: str | None = None


class ConstraintSchema(BaseModel):
    text: str


class ProblemSchema(BaseModel):
    url: str
    title: str
    difficulty: Difficulty = Difficulty.UNKNOWN
    description: str
    input_format: str | None = None
    output_format: str | None = None
    examples: list[ExampleSchema] = Field(default_factory=list)
    constraints: list[ConstraintSchema] = Field(default_factory=list)
    starter_code: str | None = None
    function_signature: str | None = None
    language: Language = Language.PYTHON
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class PlanSchema(BaseModel):
    data_structures: list[str] = Field(default_factory=list)
    algorithm_strategy: str
    time_complexity: str
    space_complexity: str
    edge_cases: list[str] = Field(default_factory=list)
    reasoning: str


class GeneratedSolutionSchema(BaseModel):
    code: str
    language: Language
    explanation: str
    plan: PlanSchema | None = None
    attempt_number: int = 1


class FailedTestCase(BaseModel):
    input: str
    expected_output: str
    actual_output: str | None = None


class ErrorSchema(BaseModel):
    error_type: ErrorType
    raw_message: str
    failed_test_cases: list[FailedTestCase] = Field(default_factory=list)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class RetrySchema(BaseModel):
    attempt_number: int
    previous_code: str
    error: ErrorSchema
    new_code: str | None = None
    prompt_used: str | None = None


class ExecutionLogSchema(BaseModel):
    session_id: str
    step: str
    message: str
    level: str = "INFO"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionSchema(BaseModel):
    session_id: str
    problem: ProblemSchema | None = None
    status: WorkflowStatus = WorkflowStatus.IDLE
    current_code: str | None = None
    retry_count: int = 0
    max_retries: int = 5
    errors: list[ErrorSchema] = Field(default_factory=list)
    final_solution: GeneratedSolutionSchema | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class BatchProblemResult(BaseModel):
    url: str
    title: str | None = None
    status: WorkflowStatus
    retry_count: int = 0
    error_summary: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class BatchStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


class BatchSessionSchema(BaseModel):
    batch_id: str
    status: BatchStatus = BatchStatus.IDLE
    language: Language = Language.PYTHON
    max_retries: int = 5
    max_problems: int | None = None
    queue: list[str] = Field(default_factory=list)  # explicit URLs; empty = use site "next" nav
    current_index: int = 0
    current_url: str | None = None
    results: list[BatchProblemResult] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


# ---- LangGraph shared state ----
class AgentState(BaseModel):
    """The single state object threaded through every LangGraph node."""
    session_id: str
    url: str = ""
    language: Language = Language.PYTHON
    problem: ProblemSchema | None = None
    plan: PlanSchema | None = None
    solution: GeneratedSolutionSchema | None = None
    formatted_code: str | None = None
    test_result_raw: str | None = None
    error: ErrorSchema | None = None
    retry_count: int = 0
    max_retries: int = 5
    status: WorkflowStatus = WorkflowStatus.IDLE
    logs: list[str] = Field(default_factory=list)
    user_requested_run: bool = False
    success: bool = False
