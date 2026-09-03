"""
FastAPI backend exposing the coding practice agent workflow.

Endpoints:
  GET  /api/problem/current      - read current browser tab & parse problem
  POST /api/solution/generate    - run full solve pipeline (read->plan->generate->format->paste)
  POST /api/editor/paste         - paste arbitrary code into the editor
  POST /api/workflow/run-tests   - user-triggered: click Run, analyze, retry-loop if needed
  GET  /api/logs/{session_id}    - execution log timeline
  GET  /api/attempts/{session_id}- all attempts for a session
  GET  /api/memory/solutions     - all previously solved problems
  GET  /api/session/{session_id} - current session state
"""
from __future__ import annotations

import asyncio
import sys

# Playwright spawns a subprocess (its browser driver) under the hood. On Windows,
# asyncio's default SelectorEventLoop cannot create subprocesses — only the
# ProactorEventLoop can. uvicorn/WatchFiles can otherwise leave the wrong policy
# active, causing `NotImplementedError` when Playwright tries to connect.
# This must be set before any event loop is created, so it lives at the very
# top of the entrypoint module.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.browser.dom_parser import DomParser
from backend.browser.playwright_manager import BrowserManager
from backend.langgraph.graph import run_solve_workflow, run_test_workflow
from backend.memory import repository
from backend.memory.db import init_db
from backend.schemas.models import AgentState, BatchSessionSchema, Language, WorkflowStatus
from backend.services import batch_orchestrator
from backend.utils.logger import get_logger

logger = get_logger("api")

# In-memory session cache (session_id -> AgentState). SQLite is the durable store.
_SESSIONS: dict[str, AgentState] = {}

# Guards against overlapping requests for the same session corrupting shared
# browser/editor state (e.g. a double-click or a Streamlit rerun firing the
# same request twice while the first is still running).
_SESSION_LOCKS: dict[str, asyncio.Lock] = {}


def _lock_for(session_id: str) -> asyncio.Lock:
    if session_id not in _SESSION_LOCKS:
        _SESSION_LOCKS[session_id] = asyncio.Lock()
    return _SESSION_LOCKS[session_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(title="AI Coding Practice Browser Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateSolutionRequest(BaseModel):
    language: Language = Language.PYTHON
    max_retries: int = 5
    session_id: str | None = None


class PasteCodeRequest(BaseModel):
    code: str


class RunTestsRequest(BaseModel):
    session_id: str


class StartBatchRequest(BaseModel):
    language: Language = Language.PYTHON
    max_retries: int = 5
    max_problems: int | None = None
    # Explicit list of problem URLs to work through in order. If empty, the
    # agent solves whatever's currently open, then clicks the site's own
    # "next problem" control after each one, until it can't find one or
    # max_problems is hit.
    queue: list[str] = []


@app.get("/api/problem/current")
async def get_current_problem():
    browser = BrowserManager()
    try:
        await browser.connect()
        parser = DomParser(browser)
        problem = await parser.parse_current_problem()
        return problem.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to read current problem")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await browser.disconnect()


@app.post("/api/solution/generate")
async def generate_solution(req: GenerateSolutionRequest):
    session_id = req.session_id or str(uuid.uuid4())
    lock = _lock_for(session_id)
    if lock.locked():
        raise HTTPException(status_code=409, detail="A request for this session is already in progress.")
    async with lock:
        try:
            state = await run_solve_workflow(session_id, req.language.value, req.max_retries)
            _SESSIONS[session_id] = state
            return state.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Solve workflow failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/editor/paste")
async def paste_code(req: PasteCodeRequest):
    browser = BrowserManager()
    try:
        await browser.connect()
        await browser.replace_editor_code(req.code)
        return {"status": "pasted"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await browser.disconnect()


@app.post("/api/workflow/run-tests")
async def run_tests(req: RunTestsRequest):
    state = _SESSIONS.get(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found. Generate a solution first.")

    lock = _lock_for(req.session_id)
    if lock.locked():
        raise HTTPException(status_code=409, detail="A request for this session is already in progress.")
    async with lock:
        try:
            updated_state = await run_test_workflow(state)
            _SESSIONS[req.session_id] = updated_state
            return updated_state.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Test workflow failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/logs/{session_id}")
async def get_logs(session_id: str):
    return await repository.get_logs(session_id)


@app.get("/api/attempts/{session_id}")
async def get_attempts(session_id: str):
    return await repository.get_attempts_for_session(session_id)


@app.get("/api/memory/solutions")
async def get_memory_solutions():
    return await repository.get_all_solutions()


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state.model_dump(mode="json")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---- Batch / loop mode ----
# Solves multiple problems in sequence with no pause for human input between
# them — including clicking Submit after a successful run, and advancing to
# the next problem. This is fully opt-in: the interactive dashboard endpoints
# above (/api/solution/generate, /api/workflow/run-tests) never submit and
# always stop for manual review; only Batch Mode submits automatically.

@app.post("/api/batch/start")
async def start_batch(req: StartBatchRequest):
    if not req.queue and req.max_problems is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either a queue of problem URLs or a max_problems limit, "
            "so the batch has a defined stopping point.",
        )
    try:
        batch_id = batch_orchestrator.start_batch(
            language=req.language.value,
            max_retries=req.max_retries,
            max_problems=req.max_problems,
            queue=req.queue,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"batch_id": batch_id}


@app.get("/api/batch/status/{batch_id}")
async def batch_status(batch_id: str):
    batch = batch_orchestrator.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch.model_dump(mode="json")


@app.post("/api/batch/stop/{batch_id}")
async def stop_batch(batch_id: str):
    stopped = batch_orchestrator.stop_batch(batch_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Batch not found or not running")
    return {"status": "stopping"}
