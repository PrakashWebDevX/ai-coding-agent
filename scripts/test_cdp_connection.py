"""
Standalone diagnostic — isolates the Playwright <-> Chrome CDP connection from
the rest of the app. Run this directly to see exactly what happens, with
timing, independent of FastAPI/LangGraph/asyncio-in-uvicorn complexity.

Usage:
    uv run python scripts/test_cdp_connection.py
"""
import asyncio
import sys
import time

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright  # noqa: E402


async def main():
    print("Starting Playwright...")
    t0 = time.time()
    pw = await async_playwright().start()
    print(f"  Playwright started in {time.time() - t0:.2f}s")

    print("Connecting to Chrome over CDP at http://127.0.0.1:9222 ...")
    t0 = time.time()
    try:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=15000)
        print(f"  Connected in {time.time() - t0:.2f}s")
    except Exception as exc:
        print(f"  FAILED after {time.time() - t0:.2f}s: {exc}")
        await pw.stop()
        return

    print(f"Contexts: {len(browser.contexts)}")
    for i, ctx in enumerate(browser.contexts):
        print(f"  Context {i}: {len(ctx.pages)} pages")
        for page in ctx.pages:
            print(f"    - {page.url}")

    await browser.close()
    await pw.stop()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())