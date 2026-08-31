"""
Browser automation core.

Attaches to an ALREADY RUNNING Chrome instance via the remote debugging port
(chrome --remote-debugging-port=9222). This agent never launches its own
browser profile for the practice workflow — the user opens the problem
themselves, and the agent reads/writes into that same tab.

The agent NEVER clicks Submit. Only Run.
"""
from __future__ import annotations

from playwright.async_api import BrowserContext, Page, async_playwright

from backend.config.selectors import SITE_PROFILES, SiteSelectors, get_selectors_for_url
from backend.config.settings import get_settings
from backend.utils.logger import get_logger, log_browser

logger = get_logger("browser")


class ElementNotFoundError(Exception):
    pass


class BrowserManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def connect(self) -> Page:
        """Attach to the existing Chrome instance over CDP and grab the active tab."""
        self._playwright = await async_playwright().start()
        # Use 127.0.0.1 explicitly rather than "localhost" — on Windows,
        # "localhost" often resolves to the IPv6 loopback (::1) first, but
        # Chrome's remote debugging server only binds to IPv4, causing
        # ECONNREFUSED even though the port is genuinely open.
        cdp_url = f"http://127.0.0.1:{self.settings.chrome_remote_debug_port}"
        log_browser(logger, f"Connecting to Chrome over CDP at {cdp_url}")

        self._browser = await self._playwright.chromium.connect_over_cdp(
            cdp_url, timeout=self.settings.browser_timeout_ms
        )
        self._context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()

        pages = self._context.pages
        if not pages:
            raise RuntimeError("No open tabs found. Open the coding problem in Chrome first.")

        self._page = await self._pick_problem_tab(pages)
        log_browser(logger, f"Attached to tab: {self._page.url}")
        return self._page

    # URLs that are clearly part of this project's own tooling, never the problem itself.
    _OWN_TOOLING_URL_FRAGMENTS = ("localhost:8501", "localhost:8000", "127.0.0.1:8501", "127.0.0.1:8000")

    async def _pick_problem_tab(self, pages: list[Page]):
        """Pick the most likely 'coding problem' tab, skipping our own dashboard/backend tabs.

        Preference order: (1) a tab whose URL matches a known site profile (leetcode.com etc.),
        (2) any tab that isn't our own tooling, (3) the last tab as a last resort.
        """
        candidates = [p for p in pages if not any(frag in p.url for frag in self._OWN_TOOLING_URL_FRAGMENTS)]

        if not candidates:
            raise RuntimeError(
                "No problem tab found — only the dashboard/backend tabs are open. "
                "Open your coding problem in a separate Chrome tab first."
            )

        known_hosts = [h for h in SITE_PROFILES if h != "default"]
        for page in candidates:
            if any(host in page.url for host in known_hosts):
                return page

        return candidates[-1]

    async def disconnect(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not connected. Call connect() first.")
        return self._page

    def selectors(self) -> SiteSelectors:
        return get_selectors_for_url(self.page.url)

    async def _first_matching(self, candidates: list[str], timeout: int = 5000):
        """Try each selector in order, returning the first that resolves to a visible element."""
        for selector in candidates:
            try:
                locator = self.page.locator(selector).first
                await locator.wait_for(state="visible", timeout=timeout)
                return locator
            except Exception:  # noqa: BLE001
                continue
        raise ElementNotFoundError(f"None of the selectors matched: {candidates}")

    async def get_page_html(self) -> str:
        return await self.page.content()

    async def get_current_url(self) -> str:
        return self.page.url

    # ---- Editor operations ----
    async def replace_editor_code(self, new_code: str) -> None:
        """Clear the Monaco editor completely and paste new code."""
        sel = self.selectors()
        editor = await self._first_matching(sel.monaco_editor, timeout=self.settings.browser_timeout_ms)
        log_browser(logger, "Clearing existing editor content")

        await editor.click()
        select_all = "Meta+A" if await self._is_mac() else "Control+A"
        await self.page.keyboard.press(select_all)
        await self.page.keyboard.press("Delete")

        log_browser(logger, "Pasting new solution into editor")
        await self.page.keyboard.insert_text(new_code)

    async def _is_mac(self) -> bool:
        ua = await self.page.evaluate("navigator.userAgent")
        return "Mac" in ua

    # ---- Test execution ----
    async def click_run(self) -> None:
        sel = self.selectors()
        button = await self._first_matching(sel.run_button, timeout=self.settings.browser_timeout_ms)
        log_browser(logger, "Clicking Run")
        await button.click()

    async def wait_for_run_completion(self, timeout_ms: int | None = None) -> None:
        sel = self.selectors()
        timeout_ms = timeout_ms or self.settings.browser_timeout_ms
        try:
            result = await self._first_matching(sel.result_container, timeout=timeout_ms)
            await result.wait_for(state="visible", timeout=timeout_ms)
        except ElementNotFoundError:
            log_browser(logger, "Result container not detected within timeout; proceeding to read whatever is present")

    async def read_result(self) -> dict:
        """Read run output: result summary, error text, failed test cases, console output."""
        sel = self.selectors()
        result_text = await self._safe_text(sel.result_container)
        error_text = await self._safe_text(sel.error_container)
        failed_cases_text = await self._safe_text(sel.failed_testcase_container)
        console_text = await self._safe_text(sel.console_output)

        return {
            "result_text": result_text,
            "error_text": error_text,
            "failed_cases_text": failed_cases_text,
            "console_text": console_text,
        }

    async def _safe_text(self, candidates: list[str]) -> str | None:
        try:
            locator = await self._first_matching(candidates, timeout=2000)
            return await locator.inner_text()
        except ElementNotFoundError:
            return None

    # NOTE: intentionally NO click_submit() method exists in this class.
    # Submission is always manual, by design (see PRD).
