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
import asyncio
import sys

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
from backend.schemas.models import AgentState, Language, WorkflowStatus
from backend.utils.logger import get_logger

logger = get_logger("api")

# In-memory session cache (session_id -> AgentState). SQLite is the durable store.
_SESSIONS: dict[str, AgentState] = {}


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
