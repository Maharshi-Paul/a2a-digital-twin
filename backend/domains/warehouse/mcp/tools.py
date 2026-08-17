"""Warehouse MCP tools — domain-specific tool implementations.

Inherits from core BaseMCPToolRegistry and registers warehouse tools
for inventory, worker, zone, packing, and dock queries.
"""

from __future__ import annotations

import logging

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.mcp.registry import BaseMCPToolRegistry
from domains.warehouse.models.inventory_item import SKU
from domains.warehouse.models.warehouse import (
    DockDoor,
    PackingStation,
    Shelf,
    Worker,
    WorkerStatus,
    Zone,
)

logger = logging.getLogger(__name__)


class WarehouseMCPToolRegistry(BaseMCPToolRegistry):
    """MCP tool registry with warehouse-specific tools."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        super().__init__()
        self.session_factory = session_factory
        self._register_all()

    def _register_all(self) -> None:
        """Register all warehouse tools."""
        self.register_tool(
            "get_inventory_for_sku",
            "Get inventory levels for a specific SKU across all shelves",
            self._get_inventory_for_sku,
        )
        self.register_tool(
            "get_all_workers",
            "Get status and location of all warehouse workers",
            self._get_all_workers,
        )
        self.register_tool(
            "get_zone_congestion",
            "Get congestion levels for all warehouse zones",
            self._get_zone_congestion,
        )
        self.register_tool(
            "get_packing_status",
            "Get load and availability of all packing stations",
            self._get_packing_status,
        )
        self.register_tool(
            "get_dock_status",
            "Get status of all dock doors",
            self._get_dock_status,
        )
        self.register_tool(
            "get_available_workers",
            "Get list of idle workers available for task assignment",
            self._get_available_workers,
        )
        self.register_tool(
            "search_sku",
            "Search for SKUs by name or category",
            self._search_sku,
        )

    # ── Tool Handlers ──────────────────────────────────────────────────

    async def _get_inventory_for_sku(self, sku_id: int) -> dict:
        async with self.session_factory() as session:
            stmt = select(Shelf).where(Shelf.sku_id == sku_id, Shelf.quantity > 0)
            result = await session.execute(stmt)
            shelves = list(result.scalars())
            return {
                "sku_id": sku_id,
                "total_quantity": sum(s.quantity for s in shelves),
                "locations": [
                    {
                        "shelf_id": s.id,
                        "aisle": s.aisle,
                        "rack": s.rack,
                        "level": s.level,
                        "quantity": s.quantity,
                        "zone_id": s.zone_id,
                    }
                    for s in shelves
                ],
            }

    async def _get_all_workers(self) -> list[dict]:
        async with self.session_factory() as session:
            result = await session.execute(select(Worker))
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "status": w.status.value,
                    "zone_id": w.current_zone_id,
                    "task_count": w.task_count,
                    "pos": [w.position_x, w.position_y],
                }
                for w in result.scalars()
            ]

    async def _get_zone_congestion(self) -> list[dict]:
        async with self.session_factory() as session:
            result = await session.execute(select(Zone))
            return [
                {
                    "id": z.id,
                    "name": z.name,
                    "congestion": round(z.congestion_level, 3),
                }
                for z in result.scalars()
            ]

    async def _get_packing_status(self) -> list[dict]:
        async with self.session_factory() as session:
            result = await session.execute(select(PackingStation))
            return [
                {
                    "id": ps.id,
                    "name": ps.name,
                    "capacity": ps.capacity,
                    "current_load": ps.current_load,
                    "status": ps.status.value,
                    "utilization": round(
                        ps.current_load / ps.capacity, 2
                    ) if ps.capacity > 0 else 0.0,
                }
                for ps in result.scalars()
            ]

    async def _get_dock_status(self) -> list[dict]:
        async with self.session_factory() as session:
            result = await session.execute(select(DockDoor))
            return [
                {
                    "id": d.id,
                    "name": d.name,
                    "status": d.status.value,
                    "truck_id": d.truck_id,
                }
                for d in result.scalars()
            ]

    async def _get_available_workers(self) -> list[dict]:
        async with self.session_factory() as session:
            stmt = select(Worker).where(Worker.status == WorkerStatus.IDLE)
            result = await session.execute(stmt)
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "zone_id": w.current_zone_id,
                    "task_count": w.task_count,
                }
                for w in result.scalars()
            ]

    async def _search_sku(self, query: str) -> list[dict]:
        async with self.session_factory() as session:
            stmt = select(SKU).where(
                SKU.name.ilike(f"%{query}%") | SKU.category.ilike(f"%{query}%")
            ).limit(20)
            result = await session.execute(stmt)
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "category": s.category,
                    "weight_kg": s.weight_kg,
                }
                for s in result.scalars()
            ]
