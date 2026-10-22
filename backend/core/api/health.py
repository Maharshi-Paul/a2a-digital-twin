"""Health check endpoint — domain-agnostic with optional detailed inspection."""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import text

from core.database import async_session_factory

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(detailed: bool = Query(False, description="Run active database probe")):
    """Basic health check for container probes, extended with optional detailed inspection."""
    if not detailed:
        return {"status": "healthy"}

    checks: dict[str, str] = {"app": "ok"}
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:80]}"

    is_healthy = checks.get("database") == "ok"
    return {
        "status": "healthy" if is_healthy else "degraded",
        "checks": checks,
    }
