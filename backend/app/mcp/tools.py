"""MCP (Model Context Protocol) tool definitions.

Defines the standardized tool interface between AI agents and
warehouse infrastructure. Each tool is a Python coroutine that
can be registered and invoked by agents.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.order import Order, OrderStatus
from app.models.sku import SKU
from app.models.warehouse import (
    DockDoor,
    PackingStation,
    Shelf,
    Worker,
    WorkerStatus,
    Zone,
)

logger = logging.getLogger(__name__)


class MCPToolRegistry:
    """Registry of MCP tools available to agents."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory
        self._tools: dict[str, dict[str, Any]] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register all built-in MCP tools."""
        self._tools = {
            "query_inventory": {
                "description": "Query real-time inventory for a SKU",
                "handler": self.query_inventory,
            },
            "get_shelf_locations": {
                "description": "Get shelf locations for a SKU",
                "handler": self.get_shelf_locations,
            },
            "get_worker_status": {
                "description": "Get current status of all workers",
                "handler": self.get_worker_status,
            },
            "get_zone_congestion": {
                "description": "Get congestion levels for all zones",
                "handler": self.get_zone_congestion,
            },
            "get_packing_status": {
                "description": "Get packing station utilization",
                "handler": self.get_packing_status,
            },
            "get_dock_status": {
                "description": "Get dock door status",
                "handler": self.get_dock_status,
            },
            "update_zone_congestion": {
                "description": "Update congestion level for a zone",
                "handler": self.update_zone_congestion,
            },
        }

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

    # ── Tool Implementations ───────────────────────────────────────

    async def query_inventory(self, sku_id: int) -> dict:
        """Query real-time inventory for a specific SKU."""
        async with self.session_factory() as session:
            sku = await session.get(SKU, sku_id)
            if not sku:
                return {"error": f"SKU {sku_id} not found"}

            stmt = select(Shelf).where(Shelf.sku_id == sku_id)
            result = await session.execute(stmt)
            shelves = list(result.scalars())

            total_qty = sum(s.quantity for s in shelves)
            return {
                "sku_id": sku_id,
                "name": sku.name,
                "category": sku.category,
                "total_quantity": total_qty,
                "locations": len(shelves),
                "substitutes": sku.substitute_sku_ids or [],
            }

    async def get_shelf_locations(self, sku_id: int) -> list[dict]:
        """Get all shelf locations holding a specific SKU."""
        async with self.session_factory() as session:
            stmt = select(Shelf).where(Shelf.sku_id == sku_id, Shelf.quantity > 0)
            result = await session.execute(stmt)
            return [
                {
                    "shelf_id": s.id,
                    "zone_id": s.zone_id,
                    "aisle": s.aisle,
                    "rack": s.rack,
                    "level": s.level,
                    "quantity": s.quantity,
                }
                for s in result.scalars()
            ]

    async def get_worker_status(self) -> list[dict]:
        """Get current status of all workers."""
        async with self.session_factory() as session:
            stmt = select(Worker)
            result = await session.execute(stmt)
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "status": w.status.value,
                    "zone_id": w.current_zone_id,
                    "task_count": w.task_count,
                    "position": {"x": w.position_x, "y": w.position_y},
                }
                for w in result.scalars()
            ]

    async def get_zone_congestion(self) -> list[dict]:
        """Get congestion levels for all zones."""
        async with self.session_factory() as session:
            stmt = select(Zone)
            result = await session.execute(stmt)
            return [
                {
                    "id": z.id,
                    "name": z.name,
                    "congestion_level": z.congestion_level,
                }
                for z in result.scalars()
            ]

    async def get_packing_status(self) -> list[dict]:
        """Get packing station utilization."""
        async with self.session_factory() as session:
            stmt = select(PackingStation)
            result = await session.execute(stmt)
            return [
                {
                    "id": ps.id,
                    "name": ps.name,
                    "capacity": ps.capacity,
                    "current_load": ps.current_load,
                    "status": ps.status.value,
                    "utilization": round(ps.current_load / ps.capacity, 2)
                    if ps.capacity > 0
                    else 0,
                }
                for ps in result.scalars()
            ]

    async def get_dock_status(self) -> list[dict]:
        """Get dock door status."""
        async with self.session_factory() as session:
            stmt = select(DockDoor)
            result = await session.execute(stmt)
            return [
                {
                    "id": d.id,
                    "name": d.name,
                    "status": d.status.value,
                    "truck_id": d.truck_id,
                }
                for d in result.scalars()
            ]

    async def update_zone_congestion(self, zone_id: int, level: float) -> dict:
        """Update congestion level for a zone."""
        async with self.session_factory() as session:
            zone = await session.get(Zone, zone_id)
            if not zone:
                return {"error": f"Zone {zone_id} not found"}
            zone.congestion_level = max(0.0, min(1.0, level))
            await session.commit()
            return {
                "zone_id": zone_id,
                "name": zone.name,
                "congestion_level": zone.congestion_level,
            }
