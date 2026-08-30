import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.schemas.models import (  # noqa: E402
    AgentState,
    ConstraintSchema,
    Difficulty,
    ExampleSchema,
    Language,
    ProblemSchema,
)


@pytest.fixture
def sample_problem() -> ProblemSchema:
    return ProblemSchema(
        url="https://leetcode.com/problems/two-sum/",
        title="Two Sum",
        difficulty=Difficulty.EASY,
        description="Given an array of integers nums and an integer target, return indices of "
        "the two numbers such that they add up to target.\n\nExample 1:\nInput: nums = [2,7,11,15], "
        "target = 9\nOutput: [0,1]\nExplanation: nums[0] + nums[1] == 9\n\nConstraints:\n"
        "2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9",
        examples=[ExampleSchema(input="nums = [2,7,11,15], target = 9", output="[0,1]")],
        constraints=[ConstraintSchema(text="2 <= nums.length <= 10^4")],
        starter_code="def twoSum(self, nums: List[int], target: int) -> List[int]:\n    pass",
        function_signature="def twoSum(self, nums: List[int], target: int) -> List[int]:",
        language=Language.PYTHON,
    )


@pytest.fixture
def base_state(sample_problem) -> AgentState:
    return AgentState(session_id="test-session", url=sample_problem.url, problem=sample_problem)
