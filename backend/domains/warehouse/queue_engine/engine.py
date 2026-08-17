"""Warehouse Queue Engine — periodic priority scoring and Redis sync.

Scores all pending/queued orders every tick, updates Redis sorted set,
and broadcasts QUEUE_UPDATE to all agents.
"""

from __future__ import annotations

import logging

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.a2a.message_bus import MessageBus
from core.a2a.protocol import A2AMessage, MessageType
from core.config import settings
from core.queue_engine.base import BaseQueueEngine
from domains.warehouse.models.order import Order, OrderStatus
from domains.warehouse.models.warehouse import (
    PackingStation,
    Shelf,
    Zone,
)
from domains.warehouse.queue_engine.scorer import (
    PriorityWeights,
    ScoredOrder,
    ScoringContext,
    score_order,
)

logger = logging.getLogger(__name__)

QUEUE_KEY = "warehouse:priority_queue"


class WarehouseQueueEngine(BaseQueueEngine):
    """Warehouse-specific queue engine with 5-factor priority scoring."""

    def __init__(
        self,
        bus: MessageBus,
        session_factory: async_sessionmaker,
        tick_seconds: float = settings.queue_tick_seconds,
    ) -> None:
        super().__init__(bus, tick_seconds)
        self.session_factory = session_factory
        self._weights = PriorityWeights()
        self._last_scored: list[ScoredOrder] = []

    async def _tick(self) -> None:
        """Score all pending/queued orders this cycle."""
        async with self.session_factory() as session:
            # Fetch orders to score
            stmt = select(Order).where(
                Order.status.in_([OrderStatus.PENDING, OrderStatus.QUEUED])
            )
            result = await session.execute(stmt)
            orders = list(result.scalars())

            if not orders:
                return

            # Get global context
            avg_congestion = await self._avg_congestion(session)
            packing_util = await self._packing_utilization(session)

            scored: list[ScoredOrder] = []
            redis_scores: dict[str, float] = {}

            for order in orders:
                # Compute per-order inventory readiness
                inv_readiness = await self._inventory_readiness(session, order)

                ctx = ScoringContext(
                    order_id=order.id,
                    external_id=order.external_id,
                    sla_deadline=order.sla_deadline,
                    created_at=order.created_at,
                    inventory_readiness=inv_readiness,
                    zone_congestion=avg_congestion,
                    packing_utilization=packing_util,
                )
                result_score = score_order(ctx, self._weights)
                scored.append(result_score)
                redis_scores[str(order.id)] = result_score.total_score

                # Update order's stored priority
                order.priority_score = result_score.total_score
                if order.status == OrderStatus.PENDING:
                    order.status = OrderStatus.QUEUED

            await session.commit()

        # Sort by score descending
        scored.sort(key=lambda s: s.total_score, reverse=True)
        self._last_scored = scored

        # Update Redis sorted set
        await self.bus.update_priority_queue(QUEUE_KEY, redis_scores)

        # Broadcast queue update
        await self.bus.broadcast(
            A2AMessage(
                sender="queue_engine",
                receiver="*",
                msg_type=MessageType.QUEUE_UPDATE,
                payload={
                    "cycle": self.cycle_count,
                    "scored_count": len(scored),
                    "top_order_id": scored[0].order_id if scored else None,
                    "top_score": scored[0].total_score if scored else 0.0,
                    "ranked_order_ids": [s.order_id for s in scored[:10]],
                },
            )
        )

        logger.info(
            "Queue cycle %d: scored %d orders (top: %s @ %.4f)",
            self.cycle_count,
            len(scored),
            scored[0].external_id if scored else "N/A",
            scored[0].total_score if scored else 0.0,
        )

    # ── Context Helpers ────────────────────────────────────────────────

    async def _avg_congestion(self, session) -> float:
        """Average congestion across all zones."""
        result = await session.execute(
            select(sqlfunc.avg(Zone.congestion_level))
        )
        return float(result.scalar() or 0.0)

    async def _packing_utilization(self, session) -> float:
        """Overall packing station utilization."""
        result = await session.execute(select(PackingStation))
        stations = list(result.scalars())
        if not stations:
            return 0.0
        total_cap = sum(s.capacity for s in stations)
        total_load = sum(s.current_load for s in stations)
        return total_load / total_cap if total_cap > 0 else 1.0

    async def _inventory_readiness(self, session, order: Order) -> float:
        """Fraction of order items fully available in inventory."""
        if not order.items:
            return 1.0
        available = 0
        for item in order.items:
            stmt = select(sqlfunc.sum(Shelf.quantity)).where(
                Shelf.sku_id == item.sku_id
            )
            result = await session.execute(stmt)
            total = result.scalar() or 0
            if total >= item.quantity:
                available += 1
        return available / len(order.items)

    # ── Public API ─────────────────────────────────────────────────────

    def get_last_scored(self) -> list[ScoredOrder]:
        return self._last_scored
