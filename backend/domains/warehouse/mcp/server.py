"""FastAPI adapter for MCP tool invocation over HTTP."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP"])

# Set at startup
_registry = None


def set_mcp_registry(registry) -> None:
    global _registry
    _registry = registry


class ToolInvokeRequest(BaseModel):
    tool_name: str
    parameters: dict[str, Any] = {}


@router.get("/tools")
async def list_tools():
    """List all available MCP tools."""
    if not _registry:
        raise HTTPException(503, "MCP registry not initialized")
    return _registry.list_tools()


@router.post("/invoke")
async def invoke_tool(req: ToolInvokeRequest):
    """Invoke an MCP tool by name with parameters."""
    if not _registry:
        raise HTTPException(503, "MCP registry not initialized")
    try:
        result = await _registry.invoke(req.tool_name, **req.parameters)
        return {"tool": req.tool_name, "result": result}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("MCP tool invocation failed: %s", req.tool_name)
        raise HTTPException(500, f"Tool error: {e}")
