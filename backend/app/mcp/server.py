"""MCP Server adapter — exposes MCP tools over HTTP for agent consumption."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP"])


class ToolInvocation(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = {}


class ToolResponse(BaseModel):
    tool_name: str
    result: Any
    error: str | None = None


# The tool registry is set at startup via set_registry()
_registry = None


def set_registry(registry) -> None:
    global _registry
    _registry = registry


@router.get("/tools")
async def list_tools():
    """List all available MCP tools."""
    if not _registry:
        return {"tools": [], "error": "MCP registry not initialized"}
    return {"tools": _registry.list_tools()}


@router.post("/invoke", response_model=ToolResponse)
async def invoke_tool(request: ToolInvocation):
    """Invoke an MCP tool by name with arguments."""
    if not _registry:
        return ToolResponse(
            tool_name=request.tool_name,
            result=None,
            error="MCP registry not initialized",
        )
    try:
        result = await _registry.invoke(request.tool_name, **request.arguments)
        return ToolResponse(tool_name=request.tool_name, result=result)
    except Exception as e:
        logger.exception("MCP tool invocation failed: %s", request.tool_name)
        return ToolResponse(
            tool_name=request.tool_name, result=None, error=str(e)
        )
