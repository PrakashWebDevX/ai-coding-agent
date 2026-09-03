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


@pytest.mark.asyncio
async def test_fixes_literal_escaped_newlines(base_state):
    base_state.solution = GeneratedSolutionSchema(
        code="class Solution:\\n    def twoSum(self, nums, target):\\n        return [0, 1]",
        language=Language.PYTHON,
        explanation="test",
    )
    result_state = await code_formatter_node(base_state)
    assert "\\n" not in result_state.formatted_code
    assert "\n" in result_state.formatted_code
    assert "def twoSum" in result_state.formatted_code


@pytest.mark.asyncio
async def test_strips_redundant_listnode_when_starter_defines_it(base_state):
    base_state.problem.starter_code = (
        "class ListNode:\n"
        "    def __init__(self, val=0, next=None):\n"
        "        self.val = val\n"
        "        self.next = next\n"
    )
    base_state.solution = GeneratedSolutionSchema(
        code=(
            "class ListNode:\n"
            "    def __init__(self, val=0, next=None):\n"
            "        self.val = val\n"
            "        self.next = next\n"
            "\n"
            "class Solution:\n"
            "    def addTwoNumbers(self, l1, l2):\n"
            "        return ListNode(0)\n"
        ),
        language=Language.PYTHON,
        explanation="test",
    )
    result_state = await code_formatter_node(base_state)
    assert "class ListNode" not in result_state.formatted_code
    assert "class Solution" in result_state.formatted_code
    assert "ListNode(0)" in result_state.formatted_code  # usage preserved, only redefinition removed


@pytest.mark.asyncio
async def test_keeps_listnode_when_starter_does_not_define_it(base_state):
    base_state.problem.starter_code = "def twoSum(self, nums, target):\n    pass"
    base_state.solution = GeneratedSolutionSchema(
        code="class ListNode:\n    pass\n\nclass Solution:\n    def f(self):\n        pass\n",
        language=Language.PYTHON,
        explanation="test",
    )
    result_state = await code_formatter_node(base_state)
    assert "class ListNode" in result_state.formatted_code
