"""Repository functions wrapping SQLAlchemy CRUD for sessions, attempts, errors, solutions, logs."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from backend.memory.db import (
    AttemptRecord,
    ErrorRecord,
    ExecutionLogRecord,
    ProblemRecord,
    SessionRecord,
    SolutionRecord,
    get_session_factory,
)
from backend.schemas.models import AgentState


async def save_problem(state: AgentState) -> None:
    if state.problem is None:
        return
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            ProblemRecord(
                url=state.problem.url,
                title=state.problem.title,
                difficulty=state.problem.difficulty.value,
                description=state.problem.description,
                data=state.problem.model_dump(mode="json"),
            )
        )
        await session.commit()


async def upsert_session(state: AgentState) -> None:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(SessionRecord).where(SessionRecord.session_id == state.session_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = SessionRecord(
                session_id=state.session_id,
                problem_title=state.problem.title if state.problem else "",
                status=state.status.value,
                retry_count=state.retry_count,
                language=state.language.value,
            )
            session.add(record)
        else:
            record.status = state.status.value
            record.retry_count = state.retry_count
            if state.status.value in ("success", "failed_max_retries"):
                record.finished_at = datetime.utcnow()
        await session.commit()


async def save_attempt(state: AgentState) -> None:
    if not state.formatted_code:
        return
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            AttemptRecord(
                session_id=state.session_id,
                attempt_number=state.retry_count + 1,
                code=state.formatted_code,
                language=state.language.value,
            )
        )
        await session.commit()


async def save_error(state: AgentState) -> None:
    if state.error is None:
        return
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            ErrorRecord(
                session_id=state.session_id,
                error_type=state.error.error_type.value,
                raw_message=state.error.raw_message,
            )
        )
        await session.commit()


async def save_final_solution(state: AgentState) -> None:
    if state.solution is None:
        return
    factory = get_session_factory()
    async with factory() as session:
        complexity = ""
        if state.plan:
            complexity = f"Time: {state.plan.time_complexity}, Space: {state.plan.space_complexity}"
        session.add(
            SolutionRecord(
                session_id=state.session_id,
                code=state.formatted_code or state.solution.code,
                language=state.language.value,
                explanation=state.solution.explanation,
                complexity=complexity,
            )
        )
        await session.commit()


async def add_log(session_id: str, step: str, message: str, level: str = "INFO") -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add(ExecutionLogRecord(session_id=session_id, step=step, message=message, level=level))
        await session.commit()


async def get_logs(session_id: str) -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ExecutionLogRecord).where(ExecutionLogRecord.session_id == session_id).order_by(
                ExecutionLogRecord.timestamp
            )
        )
        return [
            {"step": r.step, "message": r.message, "level": r.level, "timestamp": r.timestamp.isoformat()}
            for r in result.scalars().all()
        ]


async def get_all_solutions() -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(SolutionRecord).order_by(SolutionRecord.created_at.desc()))
        return [
            {
                "session_id": r.session_id,
                "code": r.code,
                "language": r.language,
                "explanation": r.explanation,
                "complexity": r.complexity,
                "created_at": r.created_at.isoformat(),
            }
            for r in result.scalars().all()
        ]


async def get_attempts_for_session(session_id: str) -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(AttemptRecord).where(AttemptRecord.session_id == session_id).order_by(
                AttemptRecord.attempt_number
            )
        )
        return [
            {"attempt_number": r.attempt_number, "code": r.code, "language": r.language}
            for r in result.scalars().all()
        ]
