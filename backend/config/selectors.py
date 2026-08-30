"""
Selector configuration.

All CSS/XPath selectors used by the browser automation layer live here.
Sites change their DOM frequently, so this file is the single place to update
when a selector breaks. Each site profile provides ordered fallback lists —
the browser layer tries them in order until one matches.
"""
from pydantic import BaseModel


class SiteSelectors(BaseModel):
    """Ordered fallback selectors for one coding-practice site."""
    problem_title: list[str]
    problem_description: list[str]
    difficulty: list[str]
    examples_container: list[str]
    constraints_container: list[str]
    starter_code_container: list[str]
    monaco_editor: list[str]
    run_button: list[str]
    submit_button: list[str]
    result_container: list[str]
    error_container: list[str]
    failed_testcase_container: list[str]
    console_output: list[str]


# Generic fallback profile — works on most Monaco-based judges (LeetCode-style).
GENERIC_PROFILE = SiteSelectors(
    problem_title=["[data-cy='question-title']", "div.text-title-large", "h1"],
    problem_description=["[data-track-load='description_content']", "div.elfjS", "div.question-content"],
    difficulty=["div[diff]", ".text-difficulty-easy", ".text-difficulty-medium", ".text-difficulty-hard"],
    examples_container=["pre", ".example-block"],
    constraints_container=["p:has-text('Constraints')", "div:has-text('Constraints')"],
    starter_code_container=[".view-lines", ".monaco-editor"],
    monaco_editor=[".monaco-editor textarea.inputarea", ".monaco-editor"],
    run_button=["button[data-e2e-locator='console-run-button']", "button:has-text('Run')"],
    submit_button=["button[data-e2e-locator='console-submit-button']", "button:has-text('Submit')"],
    result_container=["[data-e2e-locator='console-result']", ".result__1lnZ"],
    error_container=[".error-message", "[data-e2e-locator='console-error']"],
    failed_testcase_container=[".testcase-panel", ".test-case-content"],
    console_output=[".output-content", "pre.output"],
)

# Registry keyed by hostname fragment; extend with more site profiles as needed.
SITE_PROFILES: dict[str, SiteSelectors] = {
    "leetcode.com": GENERIC_PROFILE,
    "default": GENERIC_PROFILE,
}


def get_selectors_for_url(url: str) -> SiteSelectors:
    for host_fragment, profile in SITE_PROFILES.items():
        if host_fragment != "default" and host_fragment in url:
            return profile
    return SITE_PROFILES["default"]
