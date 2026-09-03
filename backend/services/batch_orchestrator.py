"""
Batch/loop mode orchestrator.

Runs the autonomous solve+test+retry graph across multiple problems in sequence,
in a background asyncio task, with no pause for human input between problems.
Submission remains manual for every problem — this module never clicks Submit.

Progress is tracked in an in-memory registry the dashboard polls via
GET /api/batch/status/{batch_id}. Batches can be stopped mid-run (the stop flag
is checked between problems, not mid-problem, so the current problem always
finishes its own solve/retry cycle first).
"""
from __future__ import annotations

import asyncio
import uuid

from backend.agents.next_problem_agent import go_to_next_problem
from backend.browser.dom_parser import DomParser
from backend.browser.playwright_manager import BrowserManager
from backend.langgraph.graph import run_autonomous_workflow
from backend.memory import repository
from backend.schemas.models import BatchProblemResult, BatchSessionSchema, BatchStatus, WorkflowStatus
from backend.utils.logger import get_logger

logger = get_logger("batch_orchestrator")

_BATCHES: dict[str, BatchSessionSchema] = {}
_TASKS: dict[str, asyncio.Task] = {}


def start_batch(language: str, max_retries: int, max_problems: int | None, queue: list[str]) -> str:
    batch_id = str(uuid.uuid4())
    batch = BatchSessionSchema(
        batch_id=batch_id,
        status=BatchStatus.RUNNING,
        language=language,
        max_retries=max_retries,
        max_problems=max_problems,
        queue=queue,
    )
    _BATCHES[batch_id] = batch
    task = asyncio.create_task(_run_batch(batch_id))
    _TASKS[batch_id] = task
    return batch_id


def get_batch(batch_id: str) -> BatchSessionSchema | None:
    return _BATCHES.get(batch_id)


def stop_batch(batch_id: str) -> bool:
    batch = _BATCHES.get(batch_id)
    if batch is None or batch.status != BatchStatus.RUNNING:
        return False
    batch.status = BatchStatus.STOPPING
    batch.logs.append("Stop requested; will halt after the current problem finishes")
    return True


async def _current_tab_url() -> str | None:
    browser = BrowserManager()
    try:
        await browser.connect()
        parser = DomParser(browser)
        return await browser.get_current_url()
    finally:
        await browser.disconnect()


async def _run_batch(batch_id: str) -> None:
    batch = _BATCHES[batch_id]
    index = 0

    try:
        while True:
            if batch.status == BatchStatus.STOPPING:
                batch.status = BatchStatus.STOPPED
                batch.logs.append("Batch stopped by user request")
                break

            if batch.max_problems is not None and index >= batch.max_problems:
                batch.status = BatchStatus.COMPLETED
                batch.logs.append(f"Reached max_problems limit ({batch.max_problems})")
                break

            # Navigate to the next problem: explicit queue URL, site's own "next"
            # control, or (on the very first iteration with no queue) whatever
            # problem is already open in the browser tab.
            if batch.queue:
                if index >= len(batch.queue):
                    batch.status = BatchStatus.COMPLETED
                    batch.logs.append("Queue exhausted")
                    break
                target_url = batch.queue[index]
                browser = BrowserManager()
                try:
                    await browser.connect()
                    await browser.navigate_to(target_url)
                finally:
                    await browser.disconnect()
            elif index > 0:
                advanced = await go_to_next_problem(None)
                if not advanced:
                    batch.status = BatchStatus.COMPLETED
                    batch.logs.append("No further 'next problem' control found; stopping")
                    break

            current_url = await _current_tab_url()
            batch.current_url = current_url
            batch.current_index = index
            batch.logs.append(f"Solving problem {index + 1}: {current_url}")

            session_id = f"{batch_id}-{index}"
            result = BatchProblemResult(url=current_url or "unknown", status=WorkflowStatus.READING_PROBLEM)

            try:
                state = await run_autonomous_workflow(session_id, batch.language.value, batch.max_retries)
                result.title = state.problem.title if state.problem else None
                result.status = state.status
                result.retry_count = state.retry_count
                if state.error:
                    result.error_summary = f"{state.error.error_type.value}: {state.error.raw_message[:200]}"
                batch.logs.append(
                    f"Problem {index + 1} finished: {state.status.value} "
                    f"(retries: {state.retry_count})"
                )
            except Exception as exc:  # noqa: BLE001
                result.status = WorkflowStatus.ERROR
                result.error_summary = str(exc)[:300]
                logger.exception(f"Batch problem {index + 1} failed with an unhandled error")
                batch.logs.append(f"Problem {index + 1} failed: {exc}")

            from datetime import datetime
            result.finished_at = datetime.utcnow()
            batch.results.append(result)

            index += 1
    finally:
        from datetime import datetime
        if batch.status == BatchStatus.RUNNING:
            batch.status = BatchStatus.COMPLETED
        batch.finished_at = datetime.utcnow()
        try:
            for r in batch.results:
                await repository.add_log(
                    batch_id, "batch", f"{r.url} -> {r.status.value} (retries={r.retry_count})"
                )
        except Exception:  # noqa: BLE001
            pass
