"""Dynamic Priority Queue Engine.

Runs an async loop every QUEUE_TICK_SECONDS to:
1. Fetch all PENDING/QUEUED orders from the database
2. Gather contextual data (inventory readiness, congestion, packing)
3. Compute priority scores using the scorer module
4. Update order.priority_score in the database
5. Push ranked order IDs to Redis sorted set
6. Broadcast queue state via the message bus
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.a2a.bus import MessageBus
from app.a2a.protocol import A2AMessage, MessageType
from app.config import settings
from app.models.order import Order, OrderItem, OrderStatus
from app.models.warehouse import PackingStation, Shelf, Zone
from app.queue_engine.scorer import (
    OrderContext,
    PriorityWeights,
    ScoredOrder,
    score_orders_batch,
)

logger = logging.getLogger(__name__)

QUEUE_REDIS_KEY = "wdt:priority_queue"


class QueueEngine:
    """Continuously re-scores and ranks pending orders."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        bus: MessageBus,
        tick_seconds: float = settings.queue_tick_seconds,
    ) -> None:
        self.session_factory = session_factory
        self.bus = bus
        self.tick_seconds = tick_seconds
        self._task: asyncio.Task | None = None
        self._running = False
        self._cycle_count = 0
        self._last_scored: list[ScoredOrder] = []
        self._weights = PriorityWeights()

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the queue engine loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="queue_engine")
        logger.info(
            "Queue Engine started (tick=%.1fs, weights=%.2f/%.2f/%.2f/%.2f/%.2f)",
            self.tick_seconds,
            self._weights.w_sla_risk,
            self._weights.w_wait_time,
            self._weights.w_inventory_readiness,
            self._weights.w_aisle_congestion,
            self._weights.w_packing_capacity,
        )

    async def stop(self) -> None:
        """Stop the queue engine loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Queue Engine stopped after %d cycles", self._cycle_count)

    # ── Main Loop ──────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        """Core loop — rescore every tick."""
        while self._running:
            try:
                scored = await self._tick()
                self._last_scored = scored
                self._cycle_count += 1

                if scored:
                    # Update Redis sorted set
                    scores_map = {
                        str(s.order_id): s.total_score for s in scored
                    }
                    await self.bus.update_priority_queue(QUEUE_REDIS_KEY, scores_map)

                    # Broadcast queue update
                    await self.bus.broadcast(
                        A2AMessage(
                            sender="queue_engine",
                            receiver="*",
                            msg_type=MessageType.QUEUE_UPDATE,
                            payload={
                                "cycle": self._cycle_count,
                                "order_count": len(scored),
                                "top_5": [
                                    {
                                        "order_id": s.order_id,
                                        "external_id": s.external_id,
                                        "score": s.total_score,
                                        "sla_risk": s.sla_risk,
                                    }
                                    for s in scored[:5]
                                ],
                            },
                        )
                    )

                    if self._cycle_count % 10 == 0:
                        logger.info(
                            "Queue cycle %d: %d orders scored, top=%s (%.4f)",
                            self._cycle_count,
                            len(scored),
                            scored[0].external_id,
                            scored[0].total_score,
                        )

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Queue engine tick failed")

            await asyncio.sleep(self.tick_seconds)

    # ── Single Tick ────────────────────────────────────────────────────

    async def _tick(self) -> list[ScoredOrder]:
        """Execute a single scoring cycle."""
        async with self.session_factory() as session:
            # 1. Fetch pending/queued orders
            orders = await self._fetch_pending_orders(session)
            if not orders:
                return []

            # 2. Gather contextual data
            avg_congestion = await self._get_avg_congestion(session)
            packing_util = await self._get_packing_utilization(session)

            # 3. Build contexts
            contexts = []
            for order in orders:
                inv_readiness = await self._compute_inv_readiness(session, order)
                contexts.append(
                    OrderContext(
                        order_id=order.id,
                        external_id=order.external_id,
                        sla_deadline=order.sla_deadline,
                        created_at=order.created_at,
                        inventory_readiness=inv_readiness,
                        avg_zone_congestion=avg_congestion,
                        packing_utilization=packing_util,
                    )
                )

            # 4. Score batch
            scored = score_orders_batch(contexts, self._weights)

            # 5. Persist scores
            for s in scored:
                order_obj = next(o for o in orders if o.id == s.order_id)
                order_obj.priority_score = s.total_score
            await session.commit()

            return scored

    # ── Data Fetchers ──────────────────────────────────────────────────

    @staticmethod
    async def _fetch_pending_orders(session) -> list[Order]:
        """Fetch all orders needing scoring."""
        stmt = (
            select(Order)
            .where(Order.status.in_([OrderStatus.PENDING, OrderStatus.QUEUED]))
            .order_by(Order.created_at)
        )
        result = await session.execute(stmt)
        return list(result.scalars())

    @staticmethod
    async def _get_avg_congestion(session) -> float:
        """Get average zone congestion across the warehouse."""
        stmt = select(sqlfunc.avg(Zone.congestion_level))
        result = await session.execute(stmt)
        avg = result.scalar()
        return float(avg) if avg else 0.0

    @staticmethod
    async def _get_packing_utilization(session) -> float:
        """Get overall packing station utilization."""
        stmt = select(PackingStation)
        result = await session.execute(stmt)
        stations = list(result.scalars())
        if not stations:
            return 0.0
        total_cap = sum(s.capacity for s in stations)
        total_load = sum(s.current_load for s in stations)
        return total_load / total_cap if total_cap > 0 else 1.0

    @staticmethod
    async def _compute_inv_readiness(session, order: Order) -> float:
        """Compute inventory readiness for an order (fraction of items in stock)."""
        items = order.items
        if not items:
            return 1.0

        available = 0
        for item in items:
            stmt = select(sqlfunc.coalesce(sqlfunc.sum(Shelf.quantity), 0)).where(
                Shelf.sku_id == item.sku_id
            )
            result = await session.execute(stmt)
            total_qty = result.scalar() or 0
            if total_qty >= item.quantity:
                available += 1

        return available / len(items)

    # ── Public API ─────────────────────────────────────────────────────

    def get_last_scored(self) -> list[ScoredOrder]:
        """Return the most recent scoring results."""
        return list(self._last_scored)

    @property
    def cycle_count(self) -> int:
        return self._cycle_count
