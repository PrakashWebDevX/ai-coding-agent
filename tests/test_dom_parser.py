from backend.browser.dom_parser import DomParser


def test_extract_examples_parses_multiple_blocks():
    description = (
        "Example 1:\nInput: nums = [2,7,11,15], target = 9\nOutput: [0,1]\n\n"
        "Example 2:\nInput: nums = [3,2,4], target = 6\nOutput: [1,2]\n\n"
        "Constraints:\n2 <= nums.length <= 10^4"
    )
    examples = DomParser._extract_examples(description)
    assert len(examples) == 2
    assert examples[0].input.startswith("nums = [2,7,11,15]")
    assert examples[1].output == "[1,2]"


def test_extract_constraints_returns_lines():
    description = "Some text.\n\nConstraints:\n2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9"
    constraints = DomParser._extract_constraints(description)
    assert len(constraints) == 2
    assert "10^4" in constraints[0].text


def test_extract_function_signature_python():
    starter = "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        pass"
    sig = DomParser._extract_function_signature(starter)
    assert sig is not None
    assert "twoSum" in sig


def test_normalize_difficulty():
    assert DomParser._normalize_difficulty("Easy").value == "Easy"
    assert DomParser._normalize_difficulty("MEDIUM").value == "Medium"
    assert DomParser._normalize_difficulty(None).value == "Unknown"
