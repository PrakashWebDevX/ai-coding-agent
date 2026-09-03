"""
Diagnostic — finds candidate "next problem" buttons on the currently open
LeetCode tab and prints their real markup, so we can craft an exact selector
instead of guessing.

Usage (with a LeetCode problem tab open in the debug Chrome instance):
    uv run python scripts/inspect_next_problem_button.py
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright  # noqa: E402

FIND_CANDIDATES_JS = """
() => {
    const els = Array.from(document.querySelectorAll('a, button, div[role="button"]'));
    const results = [];
    for (const el of els) {
        const ariaLabel = el.getAttribute('aria-label') || '';
        const title = el.getAttribute('title') || '';
        const text = (el.textContent || '').trim();
        const href = el.getAttribute('href') || '';
        const hasIcon = !!el.querySelector('svg');
        const looksLikeNav = /next|prev|arrow|chevron/i.test(ariaLabel + ' ' + title + ' ' + href + ' ' + el.className);
        if (looksLikeNav || (hasIcon && text.length < 3)) {
            results.push({
                tag: el.tagName,
                ariaLabel,
                title,
                text: text.slice(0, 30),
                href,
                className: (el.className || '').toString().slice(0, 120),
                outerHTML: el.outerHTML.slice(0, 300),
            });
        }
    }
    return results.slice(0, 25);
}
"""


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=15000)
    context = browser.contexts[0]

    # Find a leetcode.com/problems/ tab, skipping our own dashboard/backend tabs.
    page = None
    for p in context.pages:
        if "leetcode.com/problems/" in p.url:
            page = p
            break
    if page is None:
        print("No leetcode.com/problems/... tab found. Open a problem first.")
        await browser.close()
        await pw.stop()
        return

    print(f"Inspecting: {page.url}\n")
    candidates = await page.evaluate(FIND_CANDIDATES_JS)

    if not candidates:
        print("No nav-like elements found with this heuristic. Try widening the JS query.")
    for i, c in enumerate(candidates):
        print(f"--- Candidate {i} ---")
        print(f"  tag: {c['tag']}")
        print(f"  aria-label: {c['ariaLabel']!r}")
        print(f"  title: {c['title']!r}")
        print(f"  text: {c['text']!r}")
        print(f"  href: {c['href']!r}")
        print(f"  class: {c['className']!r}")
        print(f"  outerHTML: {c['outerHTML']}")
        print()

    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
