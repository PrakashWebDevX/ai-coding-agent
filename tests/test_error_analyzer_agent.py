import pytest

from backend.agents.error_analyzer_agent import error_analyzer_node
from backend.schemas.models import ErrorType, WorkflowStatus


@pytest.mark.asyncio
async def test_detects_success(base_state):
    base_state.test_result_raw = "Accepted\nAll tests passed (3/3)"
    result = await error_analyzer_node(base_state)
    assert result.success is True
    assert result.status == WorkflowStatus.SUCCESS


@pytest.mark.asyncio
async def test_detects_wrong_answer(base_state):
    base_state.test_result_raw = "Wrong Answer\nInput: [1,2] Expected: [0,1] Actual: [1,0]"
    result = await error_analyzer_node(base_state)
    assert result.success is False
    assert result.error.error_type == ErrorType.WRONG_ANSWER
    assert len(result.error.failed_test_cases) == 1


@pytest.mark.asyncio
async def test_detects_runtime_error(base_state):
    base_state.test_result_raw = "Runtime Error\nTraceback (most recent call last): IndexError"
    result = await error_analyzer_node(base_state)
    assert result.error.error_type == ErrorType.RUNTIME_ERROR


@pytest.mark.asyncio
async def test_detects_tle(base_state):
    base_state.test_result_raw = "Time Limit Exceeded"
    result = await error_analyzer_node(base_state)
    assert result.error.error_type == ErrorType.TIME_LIMIT_EXCEEDED
