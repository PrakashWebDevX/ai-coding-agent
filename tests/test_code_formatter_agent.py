import pytest

from backend.agents.code_formatter_agent import code_formatter_node
from backend.schemas.models import GeneratedSolutionSchema, Language


@pytest.mark.asyncio
async def test_strips_markdown_fences(base_state):
    base_state.solution = GeneratedSolutionSchema(
        code="```python\ndef twoSum(nums, target):\n    return [0, 1]\n```",
        language=Language.PYTHON,
        explanation="test",
    )
    result_state = await code_formatter_node(base_state)
    assert "```" not in result_state.formatted_code
    assert "def twoSum" in result_state.formatted_code


@pytest.mark.asyncio
async def test_removes_leading_prose(base_state):
    base_state.solution = GeneratedSolutionSchema(
        code="Here is the solution:\n\ndef twoSum(nums, target):\n    return [0, 1]",
        language=Language.PYTHON,
        explanation="test",
    )
    result_state = await code_formatter_node(base_state)
    assert result_state.formatted_code.startswith("def twoSum")
