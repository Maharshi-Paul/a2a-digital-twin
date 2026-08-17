"""Base MCP tool registry — domain-agnostic tool registration and invocation.

Provides the framework for standardized tool access. Domain-specific
registries (e.g. WarehouseMCPToolRegistry) should inherit from this class
and register their own tools.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BaseMCPToolRegistry:
    """Base registry of MCP tools available to agents.

    Subclasses should call `register_tool()` to add domain-specific tools.
    """

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}

    def register_tool(
        self, name: str, description: str, handler: Any
    ) -> None:
        """Register a tool with a name, description, and async handler."""
        self._tools[name] = {
            "description": description,
            "handler": handler,
        }
        logger.debug("Registered MCP tool: %s", name)

    def list_tools(self) -> list[dict[str, str]]:
        """List all available MCP tools."""
        return [
            {"name": name, "description": info["description"]}
            for name, info in self._tools.items()
        ]

    async def invoke(self, tool_name: str, **kwargs) -> Any:
        """Invoke a tool by name."""
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown MCP tool: {tool_name}")
        return await tool["handler"](**kwargs)

    @property
    def tool_count(self) -> int:
        return len(self._tools)
