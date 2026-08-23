"""Warehouse Queue Engine — periodic priority scoring and Redis sync.

Scores all pending/queued orders every tick, updates Redis sorted set,
and broadcasts QUEUE_UPDATE to all agents.

Supports two modes via ``QUEUE_ENGINE_MODE``:
- ``rule_based`` (default): 5-factor weighted scoring
- ``llm_batch``: LLM-assisted batch re-ranking with rule-based fallback
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

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
from domains.warehouse.queue_engine.fifo_baseline import FIFOBaseline, QueueComparison
from domains.warehouse.queue_engine.llm_reranker import rerank as llm_rerank
from domains.warehouse.services.decision_commentary import explain_decision
from domains.warehouse.api.websocket import broadcast_decision_commentary

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
        self._fifo_baseline = FIFOBaseline()
        self._last_comparison: list[QueueComparison] = []
        # LLM batch re-ranking state
        self._llm_total_ticks: int = 0
        self._llm_fallback_ticks: int = 0

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

            # ── Rule-based scoring (always computed — serves as baseline/fallback) ──
            scored: list[ScoredOrder] = []
            inv_readiness_map: dict[int, float] = {}

            for order in orders:
                # Compute per-order inventory readiness
                inv_readiness = await self._inventory_readiness(session, order)
                inv_readiness_map[order.id] = inv_readiness

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

            # ── LLM batch re-ranking (opt-in) ──────────────────────────────
            used_llm = False

            if settings.queue_engine_mode == "llm_batch":
                self._llm_total_ticks += 1

                # Prepare minimal order data for LLM
                order_data = [
                    {
                        "external_id": order.external_id,
                        "sla_deadline": order.sla_deadline,
                        "created_at": order.created_at,
                        "inventory_readiness": inv_readiness_map.get(order.id, 1.0),
                        "item_count": len(order.items) if order.items else 1,
                    }
                    for order in orders
                ]

                # Run rerank as a tracked task
                rerank_coro = llm_rerank(
                    order_data,
                    avg_congestion=avg_congestion,
                    packing_util=packing_util,
                )
                try:
                    reranked = await rerank_coro
                except Exception:
                    logger.warning("LLM rerank raised unexpectedly", exc_info=True)
                    reranked = None

                if reranked is not None and len(reranked) > 0:
                    # Reorder scored list according to LLM's ranking
                    scored_by_eid = {s.external_id: s for s in scored}
                    reason_by_eid = {
                        r["order_id"]: r.get("reason", "") for r in reranked
                    }

                    reordered: list[ScoredOrder] = []
                    n = len(reranked)

                    for rank, entry in enumerate(reranked):
                        eid = entry["order_id"]
                        original = scored_by_eid.get(eid)
                        if original is None:
                            continue
                        # Assign position-based score: N, N-1, ..., 1 normalized to [0, 1]
                        position_score = round((n - rank) / n, 6)
                        reordered.append(
                            replace(
                                original,
                                total_score=position_score,
                                ranked_by="llm",
                                llm_reason=reason_by_eid.get(eid, ""),
                            )
                        )

                    if len(reordered) == len(scored):
                        scored = reordered
                        used_llm = True
                        logger.debug(
                            "LLM rerank applied for %d orders", len(scored)
                        )
                    else:
                        logger.warning(
                            "LLM rerank partial match (%d/%d) — using rule-based fallback",
                            len(reordered),
                            len(scored),
                        )
                        self._llm_fallback_ticks += 1
                else:
                    self._llm_fallback_ticks += 1
                    logger.debug("LLM rerank returned None — using rule-based fallback")

            # ── Update orders in DB ───────────────────────────────────────────
            scored_by_id = {s.order_id: s for s in scored}
            for order in orders:
                s = scored_by_id.get(order.id)
                if s:
                    order.priority_score = s.total_score
                if order.status == OrderStatus.PENDING:
                    order.status = OrderStatus.QUEUED

            await session.commit()

        # Sort by score descending
        scored.sort(key=lambda s: s.total_score, reverse=True)
        self._last_scored = scored

        redis_scores = {str(s.order_id): s.total_score for s in scored}

        # Update Redis sorted set
        await self.bus.update_priority_queue(QUEUE_KEY, redis_scores)

        # Broadcast queue update
        ranking_source = "llm" if used_llm else "rules"
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
                    "ranked_by": ranking_source,
                },
            )
        )

        logger.info(
            "Queue cycle %d: scored %d orders (top: %s @ %.4f) [%s]",
            self.cycle_count,
            len(scored),
            scored[0].external_id if scored else "N/A",
            scored[0].total_score if scored else 0.0,
            ranking_source,
        )

        # Fire commentary for the top-scored order (non-blocking)
        if scored:
            asyncio.create_task(self._fire_commentary(scored[0]))

        # Compute FIFO baseline and comparison
        async with self.session_factory() as session:
            await self._fifo_baseline.compute(session)
        self._last_comparison = self._fifo_baseline.compare(
            [
                {
                    "order_id": s.order_id,
                    "external_id": s.external_id,
                    "total_score": s.total_score,
                }
                for s in scored
            ]
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

    # ── Commentary (non-blocking) ──────────────────────────────────────

    async def _fire_commentary(self, top: ScoredOrder) -> None:
        """Generate and broadcast an LLM-powered explanation for the top order."""
        try:
            commentary = await explain_decision(top)
            if commentary:
                await broadcast_decision_commentary(
                    order_id=top.order_id,
                    external_id=top.external_id,
                    commentary=commentary,
                )
        except Exception:
            logger.warning("Commentary task failed", exc_info=True)

    # ── Public API ─────────────────────────────────────────────────────

    def get_last_scored(self) -> list[ScoredOrder]:
        return self._last_scored

    def get_last_comparison(self) -> list[QueueComparison]:
        """Return the last FIFO vs priority comparison."""
        return self._last_comparison

    def get_fifo_baseline(self) -> list:
        """Return the last FIFO baseline ordering."""
        return self._fifo_baseline.get_last_fifo()

    def get_engine_mode(self) -> str:
        """Return the active queue engine mode."""
        return settings.queue_engine_mode

    def get_fallback_rate(self) -> float:
        """Return the LLM fallback rate (0.0-1.0)."""
        if self._llm_total_ticks == 0:
            return 0.0
        return self._llm_fallback_ticks / self._llm_total_ticks
