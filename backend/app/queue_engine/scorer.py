"""Dynamic Priority Queue Scorer.

Implements the heuristic scoring function:
  Priority = w1*SLA_Risk + w2*Wait_Time + w3*Inventory_Readiness
           + w4*(1/Aisle_Congestion) + w5*Packing_Capacity

All component scores are normalized to [0, 1] range.
Higher score = higher priority = should be processed first.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PriorityWeights:
    """Configurable weights for the priority scoring function."""
    w_sla_risk: float = settings.w_sla_risk
    w_wait_time: float = settings.w_wait_time
    w_inventory_readiness: float = settings.w_inventory_readiness
    w_aisle_congestion: float = settings.w_aisle_congestion
    w_packing_capacity: float = settings.w_packing_capacity

    @property
    def total(self) -> float:
        return (
            self.w_sla_risk
            + self.w_wait_time
            + self.w_inventory_readiness
            + self.w_aisle_congestion
            + self.w_packing_capacity
        )


@dataclass(slots=True)
class OrderContext:
    """Contextual data needed to score a single order."""
    order_id: int
    external_id: str
    sla_deadline: datetime
    created_at: datetime
    inventory_readiness: float   # 0.0 (nothing) → 1.0 (all items in stock)
    avg_zone_congestion: float   # 0.0 (empty) → 1.0 (jammed)
    packing_utilization: float   # 0.0 (all free) → 1.0 (all full)


@dataclass(frozen=True, slots=True)
class ScoredOrder:
    """Result of scoring an order."""
    order_id: int
    external_id: str
    total_score: float
    sla_risk: float
    wait_time_norm: float
    inventory_readiness: float
    congestion_inv: float
    packing_capacity: float


DEFAULT_WEIGHTS = PriorityWeights()

# Max wait time for normalization (default 60 minutes = 3600 seconds)
MAX_WAIT_SECONDS = 3600.0


def compute_sla_risk(deadline: datetime, now: datetime | None = None) -> float:
    """Compute SLA risk factor [0, 1]. Higher = closer to breach.

    SLA_Risk = max(0, 1 - (time_remaining / sla_window))
    where sla_window is the original total time allotted.
    """
    now = now or datetime.now(timezone.utc)
    remaining = (deadline - now).total_seconds()
    if remaining <= 0:
        return 1.0  # Already breached
    # Use 60-min SLA window as baseline; adjust based on actual deadline
    sla_window = max(remaining, 60.0)  # minimum 1-minute normalization
    risk = max(0.0, 1.0 - (remaining / sla_window))
    return min(1.0, risk)


def compute_sla_risk_v2(
    deadline: datetime,
    created_at: datetime,
    now: datetime | None = None,
) -> float:
    """Improved SLA risk using original window for normalization.

    Risk = 1 - (time_remaining / total_window)
    """
    now = now or datetime.now(timezone.utc)
    total_window = (deadline - created_at).total_seconds()
    if total_window <= 0:
        return 1.0
    remaining = (deadline - now).total_seconds()
    if remaining <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (remaining / total_window)))


def compute_wait_time(
    created_at: datetime,
    now: datetime | None = None,
    max_wait: float = MAX_WAIT_SECONDS,
) -> float:
    """Compute normalized wait time [0, 1]."""
    now = now or datetime.now(timezone.utc)
    waited = (now - created_at).total_seconds()
    return min(1.0, max(0.0, waited / max_wait))


def score_order(
    ctx: OrderContext,
    weights: PriorityWeights = DEFAULT_WEIGHTS,
    now: datetime | None = None,
) -> ScoredOrder:
    """Compute dynamic priority score for an order.

    Priority = w1*SLA_Risk + w2*Wait_Time + w3*Inv_Readiness
             + w4*(1/Congestion) + w5*(1-Packing_Util)
    """
    now = now or datetime.now(timezone.utc)

    # Component 1: SLA Risk (higher = more urgent)
    sla_risk = compute_sla_risk_v2(ctx.sla_deadline, ctx.created_at, now)

    # Component 2: Wait Time (higher = waited longer)
    wait_time_norm = compute_wait_time(ctx.created_at, now)

    # Component 3: Inventory Readiness (higher = ready to pick)
    inv_readiness = ctx.inventory_readiness

    # Component 4: Inverse Aisle Congestion (higher = less congested = preferred)
    congestion_inv = max(0.0, 1.0 - ctx.avg_zone_congestion)

    # Component 5: Packing Capacity (higher = more packing slots available)
    packing_cap = max(0.0, 1.0 - ctx.packing_utilization)

    # Weighted sum
    total_score = (
        weights.w_sla_risk * sla_risk
        + weights.w_wait_time * wait_time_norm
        + weights.w_inventory_readiness * inv_readiness
        + weights.w_aisle_congestion * congestion_inv
        + weights.w_packing_capacity * packing_cap
    )

    return ScoredOrder(
        order_id=ctx.order_id,
        external_id=ctx.external_id,
        total_score=round(total_score, 6),
        sla_risk=round(sla_risk, 4),
        wait_time_norm=round(wait_time_norm, 4),
        inventory_readiness=round(inv_readiness, 4),
        congestion_inv=round(congestion_inv, 4),
        packing_capacity=round(packing_cap, 4),
    )


def score_orders_batch(
    contexts: list[OrderContext],
    weights: PriorityWeights = DEFAULT_WEIGHTS,
) -> list[ScoredOrder]:
    """Score a batch of orders and return sorted by priority (highest first)."""
    now = datetime.now(timezone.utc)
    scored = [score_order(ctx, weights, now) for ctx in contexts]
    scored.sort(key=lambda s: s.total_score, reverse=True)
    return scored
