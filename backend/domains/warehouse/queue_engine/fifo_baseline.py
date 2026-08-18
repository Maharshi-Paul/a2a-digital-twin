"""FIFO Baseline Engine — static FIFO queue comparison baseline.

Provides a pure FIFO ordering (by created_at timestamp) of pending
orders, enabling direct comparison against the 5-factor priority
queue.  Differences are logged and exposed via the comparison API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.warehouse.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FIFOScoredOrder:
    """A FIFO-ordered order (sorted by creation time only)."""
    order_id: int
    external_id: str
    created_at: datetime
    position: int  # 1-based rank in FIFO queue


@dataclass(frozen=True, slots=True)
class QueueComparison:
    """Side-by-side comparison of priority vs FIFO ordering for one order."""
    order_id: int
    external_id: str
    priority_rank: int   # Position in the 5-factor queue (1 = highest)
    fifo_rank: int       # Position in FIFO queue (1 = oldest)
    priority_score: float
    rank_delta: int      # fifo_rank - priority_rank (positive = promoted by priority queue)


class FIFOBaseline:
    """Computes a pure FIFO baseline from the same dataset the priority queue uses."""

    def __init__(self) -> None:
        self._last_fifo: list[FIFOScoredOrder] = []

    async def compute(self, session: AsyncSession) -> list[FIFOScoredOrder]:
        """Query all active orders and rank them by creation time (oldest first).

        Active statuses = PENDING, QUEUED, PICKING.
        """
        stmt = (
            select(Order)
            .where(
                Order.status.in_(
                    [OrderStatus.PENDING, OrderStatus.QUEUED, OrderStatus.PICKING]
                )
            )
            .order_by(Order.created_at.asc())
        )
        result = await session.execute(stmt)
        orders = list(result.scalars())

        self._last_fifo = [
            FIFOScoredOrder(
                order_id=o.id,
                external_id=o.external_id,
                created_at=o.created_at,
                position=i + 1,
            )
            for i, o in enumerate(orders)
        ]
        logger.debug("FIFO baseline computed: %d orders", len(self._last_fifo))
        return self._last_fifo

    def get_last_fifo(self) -> list[FIFOScoredOrder]:
        """Return the last computed FIFO baseline."""
        return list(self._last_fifo)

    def compare(
        self,
        priority_ranking: list[dict],
    ) -> list[QueueComparison]:
        """Compare the priority queue against the current FIFO baseline.

        Args:
            priority_ranking: List of dicts with keys
                ``order_id``, ``external_id``, ``total_score``.

        Returns:
            List of ``QueueComparison`` objects showing rank deltas.
        """
        fifo_rank_map = {f.order_id: f.position for f in self._last_fifo}

        comparisons = []
        for pri_rank, item in enumerate(priority_ranking, start=1):
            oid = item["order_id"]
            fifo_rank = fifo_rank_map.get(oid, -1)
            comparisons.append(
                QueueComparison(
                    order_id=oid,
                    external_id=item.get("external_id", ""),
                    priority_rank=pri_rank,
                    fifo_rank=fifo_rank,
                    priority_score=item.get("total_score", 0.0),
                    rank_delta=fifo_rank - pri_rank if fifo_rank > 0 else 0,
                )
            )

        return comparisons
