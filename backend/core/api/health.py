"""Health check endpoint — domain-agnostic."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    """Basic health check. Extended by domain-specific startup."""
    return {"status": "healthy"}
