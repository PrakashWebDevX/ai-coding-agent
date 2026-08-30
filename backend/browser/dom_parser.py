"""
Parses raw page HTML/DOM into structured problem data.

Strategy: Playwright selectors are tried first (live DOM, handles JS-rendered
content). If Playwright can't find something, BeautifulSoup parses the raw
HTML snapshot as a fallback for static fragments.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from backend.browser.playwright_manager import BrowserManager
from backend.schemas.models import ConstraintSchema, Difficulty, ExampleSchema, Language, ProblemSchema
from backend.utils.logger import get_logger

logger = get_logger("dom_parser")


class DomParser:
    def __init__(self, browser: BrowserManager) -> None:
        self.browser = browser

    async def parse_current_problem(self) -> ProblemSchema:
        sel = self.browser.selectors()
        url = await self.browser.get_current_url()
        html = await self.browser.get_page_html()
        soup = BeautifulSoup(html, "lxml")

        title = await self._extract_via_playwright_or_soup(sel.problem_title, soup)
        difficulty_raw = await self._extract_via_playwright_or_soup(sel.difficulty, soup)
        description = await self._extract_via_playwright_or_soup(sel.problem_description, soup)
        starter_code = await self._extract_via_playwright_or_soup(sel.starter_code_container, soup)

        description = description or ""
        examples = self._extract_examples(description)
        constraints = self._extract_constraints(description)
        function_signature = self._extract_function_signature(starter_code or "")

        problem = ProblemSchema(
            url=url,
            title=(title or "Untitled Problem").strip(),
            difficulty=self._normalize_difficulty(difficulty_raw),
            description=description,
            examples=examples,
            constraints=constraints,
            starter_code=starter_code,
            function_signature=function_signature,
            language=Language.PYTHON,
        )
        logger.info(f"Parsed problem: {problem.title} ({problem.difficulty})")
        return problem

    async def _extract_via_playwright_or_soup(self, candidates: list[str], soup: BeautifulSoup) -> str | None:
        try:
            locator = await self.browser._first_matching(candidates, timeout=3000)  # noqa: SLF001
            text = await locator.inner_text()
            if text and text.strip():
                return text.strip()
        except Exception:  # noqa: BLE001
            pass

        # BeautifulSoup fallback: try each selector as a CSS selector against the static HTML.
        for selector in candidates:
            try:
                css_selector = selector.split(":has-text")[0].strip() if ":has-text" in selector else selector
                node = soup.select_one(css_selector)
                if node and node.get_text(strip=True):
                    return node.get_text(" ", strip=True)
            except Exception:  # noqa: BLE001
                continue
        return None

    @staticmethod
    def _normalize_difficulty(raw: str | None) -> Difficulty:
        if not raw:
            return Difficulty.UNKNOWN
        raw_lower = raw.lower()
        if "easy" in raw_lower:
            return Difficulty.EASY
        if "medium" in raw_lower:
            return Difficulty.MEDIUM
        if "hard" in raw_lower:
            return Difficulty.HARD
        return Difficulty.UNKNOWN

    @staticmethod
    def _extract_examples(description: str) -> list[ExampleSchema]:
        examples: list[ExampleSchema] = []
        blocks = re.split(r"Example\s*\d*:?", description)[1:]
        for block in blocks:
            input_match = re.search(r"Input:?\s*(.+?)(?=Output:|$)", block, re.DOTALL)
            output_match = re.search(r"Output:?\s*(.+?)(?=Explanation:|Example|Constraints|$)", block, re.DOTALL)
            explanation_match = re.search(r"Explanation:?\s*(.+?)(?=Example|Constraints|$)", block, re.DOTALL)
            if input_match and output_match:
                examples.append(
                    ExampleSchema(
                        input=input_match.group(1).strip(),
                        output=output_match.group(1).strip(),
                        explanation=explanation_match.group(1).strip() if explanation_match else None,
                    )
                )
        return examples

    @staticmethod
    def _extract_constraints(description: str) -> list[ConstraintSchema]:
        constraints: list[ConstraintSchema] = []
        match = re.search(r"Constraints:?\s*(.+)$", description, re.DOTALL)
        if not match:
            return constraints
        block = match.group(1)
        lines = [line.strip("• -\t ") for line in block.splitlines() if line.strip()]
        for line in lines:
            if len(line) < 200:  # guard against accidentally capturing trailing unrelated content
                constraints.append(ConstraintSchema(text=line))
        return constraints

    @staticmethod
    def _extract_function_signature(starter_code: str) -> str | None:
        patterns = [
            r"def\s+\w+\([^)]*\)\s*->?\s*[\w\[\], ]*:",  # python
            r"public\s+\w[\w<>\[\], ]*\s+\w+\([^)]*\)\s*\{?",  # java
            r"\w[\w:<>]*\s+\w+\([^)]*\)\s*\{?",  # cpp
            r"function\s+\w+\([^)]*\)\s*\{?",  # javascript
        ]
        for pattern in patterns:
            match = re.search(pattern, starter_code)
            if match:
                return match.group(0).rstrip("{ ").strip()
        return None
