"""Priority scoring function for warehouse orders.

Priority = w1*SLA_Risk + w2*Wait_Time + w3*Inv_Readiness
         + w4*(1/Congestion) + w5*(1-Packing_Util)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PriorityWeights:
    """Configurable priority weights (must sum to ~1.0)."""
    w_sla_risk: float = settings.w_sla_risk
    w_wait_time: float = settings.w_wait_time
    w_inventory_readiness: float = settings.w_inventory_readiness
    w_aisle_congestion: float = settings.w_aisle_congestion
    w_packing_capacity: float = settings.w_packing_capacity


@dataclass(frozen=True, slots=True)
class ScoringContext:
    """Context data needed to score a single order."""
    order_id: int
    external_id: str
    sla_deadline: datetime
    created_at: datetime
    inventory_readiness: float   # 0-1 fraction of items in stock
    zone_congestion: float       # 0-1 average congestion of target zones
    packing_utilization: float   # 0-1 overall packing station load


@dataclass(frozen=True, slots=True)
class ScoredOrder:
    """Result of scoring an order — includes breakdown for dashboard display."""
    order_id: int
    external_id: str
    total_score: float
    sla_risk: float
    wait_time_norm: float
    inventory_readiness: float
    congestion_factor: float
    packing_factor: float
    breakdown: dict = field(default_factory=dict)


def score_order(
    ctx: ScoringContext,
    weights: PriorityWeights | None = None,
    max_wait_minutes: float = 120.0,
    max_sla_minutes: float = 60.0,
) -> ScoredOrder:
    """Compute priority score for a single order.

    All factors are normalized to [0, 1] before weighting.
    Higher score = higher priority.
    """
    if weights is None:
        weights = PriorityWeights()

    now = datetime.now(timezone.utc)

    # ── Factor 1: SLA Risk (higher = more urgent) ─────────────────────
    time_until_sla = (ctx.sla_deadline - now).total_seconds() / 60.0
    time_until_sla = max(time_until_sla, 0.0)
    sla_risk = 1.0 - min(time_until_sla / max_sla_minutes, 1.0)

    # ── Factor 2: Wait Time (longer wait = higher priority) ───────────
    wait_minutes = (now - ctx.created_at).total_seconds() / 60.0
    wait_minutes = max(wait_minutes, 0.0)
    wait_time_norm = min(wait_minutes / max_wait_minutes, 1.0)

    # ── Factor 3: Inventory Readiness (higher = easier to fulfill) ────
    inv_readiness = ctx.inventory_readiness

    # ── Factor 4: Congestion Inverse (low congestion = favorable) ─────
    congestion_inv = 1.0 - min(ctx.zone_congestion, 1.0)

    # ── Factor 5: Packing Capacity (low utilization = favorable) ──────
    packing_cap = 1.0 - min(ctx.packing_utilization, 1.0)

    # ── Weighted Sum ──────────────────────────────────────────────────
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
        congestion_factor=round(congestion_inv, 4),
        packing_factor=round(packing_cap, 4),
        breakdown={
            "sla_risk_weighted": round(weights.w_sla_risk * sla_risk, 4),
            "wait_weighted": round(weights.w_wait_time * wait_time_norm, 4),
            "inventory_weighted": round(weights.w_inventory_readiness * inv_readiness, 4),
            "congestion_weighted": round(weights.w_aisle_congestion * congestion_inv, 4),
            "packing_weighted": round(weights.w_packing_capacity * packing_cap, 4),
        },
    )
