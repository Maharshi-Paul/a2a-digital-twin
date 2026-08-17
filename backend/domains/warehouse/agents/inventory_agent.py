"""Inventory Agent — stock verification, stockout detection, and SKU substitution.

Responsibilities:
- Responds to stock-check requests from any agent
- Detects stockouts and publishes STOCKOUT_ALERT via A2A
- Proposes substitute SKUs from the SKU substitute list
- Maintains real-time view of shelf quantities
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.a2a.message_bus import MessageBus
from core.a2a.protocol import A2AMessage, MessageType
from core.agents.base import BaseAgent
from domains.warehouse.models.inventory_item import SKU
from domains.warehouse.models.warehouse import Shelf

logger = logging.getLogger(__name__)


class InventoryAgent(BaseAgent):
    """Manages inventory state, stock checks, and substitution proposals."""

    def __init__(self, bus: MessageBus, session_factory: async_sessionmaker) -> None:
        super().__init__("inventory_agent", bus, session_factory)

    async def handle_message(self, msg: A2AMessage) -> None:
        """Route incoming messages to appropriate handlers."""
        match msg.msg_type:
            case MessageType.STOCK_CHECK:
                await self._handle_stock_check(msg)
            case MessageType.SUBSTITUTE_OFFER:
                # Acknowledgment from picking agent about accepted substitute
                logger.info(
                    "[inventory] Substitute acknowledgment from %s: %s",
                    msg.sender, msg.payload,
                )
            case _:
                logger.debug("[inventory] Unhandled msg_type: %s", msg.msg_type)

    # ── Stock Check ────────────────────────────────────────────────────

    async def _handle_stock_check(self, msg: A2AMessage) -> None:
        """Check stock for a list of items and report availability."""
        order_id = msg.payload.get("order_id")
        items = msg.payload.get("items", [])
        results = []
        stockouts = []

        async with self.session_factory() as session:
            for item in items:
                sku_id = item["sku_id"]
                qty_needed = item["quantity"]

                # Sum available quantity across all shelves for this SKU
                stmt = select(Shelf).where(Shelf.sku_id == sku_id, Shelf.quantity > 0)
                result = await session.execute(stmt)
                shelves = list(result.scalars())
                total_available = sum(s.quantity for s in shelves)

                if total_available >= qty_needed:
                    results.append({
                        "sku_id": sku_id,
                        "available": True,
                        "total_qty": total_available,
                        "shelf_locations": [
                            {
                                "shelf_id": s.id,
                                "aisle": s.aisle,
                                "rack": s.rack,
                                "level": s.level,
                                "qty": s.quantity,
                            }
                            for s in shelves
                        ],
                    })
                else:
                    results.append({
                        "sku_id": sku_id,
                        "available": False,
                        "total_qty": total_available,
                        "shortage": qty_needed - total_available,
                    })
                    stockouts.append(sku_id)

        # Send stock response
        await self.reply(
            msg,
            MessageType.STOCK_RESPONSE,
            payload={
                "order_id": order_id,
                "items": results,
                "all_available": len(stockouts) == 0,
            },
        )

        # Trigger stockout flow for each missing SKU
        for sku_id in stockouts:
            await self._handle_stockout(msg.sender, order_id, sku_id)

    # ── Stockout Handling ──────────────────────────────────────────────

    async def _handle_stockout(
        self, requester: str, order_id: int, sku_id: int
    ) -> None:
        """Detect stockout and propose substitute SKUs."""
        logger.warning(
            "[inventory] STOCKOUT detected: SKU %d for order %d", sku_id, order_id
        )

        # Alert the order coordinator
        await self.send(
            "order_coordinator",
            MessageType.STOCKOUT_ALERT,
            payload={"order_id": order_id, "sku_id": sku_id},
        )

        # Find substitutes
        substitutes = await self._find_substitutes(sku_id)
        if substitutes:
            await self.send(
                requester,
                MessageType.SUBSTITUTE_OFFER,
                payload={
                    "order_id": order_id,
                    "original_sku_id": sku_id,
                    "substitutes": substitutes,
                },
            )
            logger.info(
                "[inventory] Offered %d substitutes for SKU %d",
                len(substitutes),
                sku_id,
            )
        else:
            logger.warning("[inventory] No substitutes available for SKU %d", sku_id)
            await self.send(
                requester,
                MessageType.NACK,
                payload={
                    "order_id": order_id,
                    "sku_id": sku_id,
                    "reason": "no_substitutes_available",
                },
            )

    async def _find_substitutes(self, sku_id: int) -> list[dict]:
        """Find available substitute SKUs for a stockout item."""
        async with self.session_factory() as session:
            sku = await session.get(SKU, sku_id)
            if not sku or not sku.substitute_sku_ids:
                return []

            substitutes = []
            for sub_id in sku.substitute_sku_ids:
                # Check if substitute is in stock
                stmt = select(Shelf).where(Shelf.sku_id == sub_id, Shelf.quantity > 0)
                result = await session.execute(stmt)
                shelves = list(result.scalars())
                total_qty = sum(s.quantity for s in shelves)

                if total_qty > 0:
                    sub_sku = await session.get(SKU, sub_id)
                    substitutes.append({
                        "sku_id": sub_id,
                        "name": sub_sku.name if sub_sku else "Unknown",
                        "available_qty": total_qty,
                        "shelf_locations": [
                            {"shelf_id": s.id, "aisle": s.aisle, "rack": s.rack}
                            for s in shelves[:3]  # Top 3 locations
                        ],
                    })
            return substitutes

    # ── Inventory Readiness Score ──────────────────────────────────────

    async def compute_readiness(self, sku_ids_with_qty: list[dict]) -> float:
        """Compute fraction of order items available (0.0 → 1.0)."""
        if not sku_ids_with_qty:
            return 1.0

        available_count = 0
        async with self.session_factory() as session:
            for item in sku_ids_with_qty:
                stmt = select(Shelf).where(
                    Shelf.sku_id == item["sku_id"], Shelf.quantity >= item["quantity"]
                )
                result = await session.execute(stmt)
                if result.first():
                    available_count += 1

        return available_count / len(sku_ids_with_qty)
