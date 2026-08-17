"""REST API routes for the warehouse digital twin."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from domains.warehouse.models.order import OrderStatus
from domains.warehouse.services.warehouse_service import WarehouseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Warehouse API"])

# Set at startup from main.py
_order_coordinator = None
_queue_engine = None
_generator = None


def set_api_refs(coordinator, queue_engine, generator) -> None:
    global _order_coordinator, _queue_engine, _generator
    _order_coordinator = coordinator
    _queue_engine = queue_engine
    _generator = generator


# ── Orders ──────────────────────────────────────────────────────────────

@router.get("/orders")
async def list_orders(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """List orders with optional status filter."""
    order_status = None
    if status:
        try:
            order_status = OrderStatus(status.upper())
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    return await WarehouseService.get_orders(session, order_status, limit, offset)


@router.get("/orders/counts")
async def order_counts(session: AsyncSession = Depends(get_session)):
    """Get order counts by status."""
    return await WarehouseService.get_order_count(session)


# ── Queue ───────────────────────────────────────────────────────────────

@router.get("/queue")
async def queue_status():
    """Get current priority queue state."""
    if not _queue_engine:
        raise HTTPException(503, "Queue engine not initialized")
    scored = _queue_engine.get_last_scored()
    return {
        "cycle": _queue_engine.cycle_count,
        "count": len(scored),
        "orders": [
            {
                "order_id": s.order_id,
                "external_id": s.external_id,
                "score": s.total_score,
                "sla_risk": s.sla_risk,
                "wait_time": s.wait_time_norm,
                "inventory": s.inventory_readiness,
                "congestion": s.congestion_factor,
                "packing": s.packing_factor,
                "breakdown": s.breakdown,
            }
            for s in scored[:50]
        ],
    }


# ── Warehouse Status ───────────────────────────────────────────────────

@router.get("/warehouse/status")
async def warehouse_status(session: AsyncSession = Depends(get_session)):
    """Get full warehouse status snapshot."""
    return await WarehouseService.get_warehouse_status(session)


@router.get("/warehouse/kpis")
async def warehouse_kpis(session: AsyncSession = Depends(get_session)):
    """Get real-time KPIs."""
    return await WarehouseService.get_kpis(session)


# ── Agent Logs ──────────────────────────────────────────────────────────

@router.get("/agent-logs")
async def agent_logs(
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Get recent agent communication logs."""
    return await WarehouseService.get_agent_logs(session, limit)


# ── Simulation Controls ────────────────────────────────────────────────

@router.post("/simulation/seed")
async def seed_simulation(session: AsyncSession = Depends(get_session)):
    """Seed the warehouse database with simulation data."""
    from domains.warehouse.simulation.seeder import seed_database
    result = await seed_database(session)
    return {"status": "seeded", "counts": result}


@router.post("/simulation/start")
async def start_simulation():
    """Start the order generator."""
    if not _generator:
        raise HTTPException(503, "Generator not initialized")
    if _generator.is_running:
        return {"status": "already_running"}
    await _generator.start()
    return {"status": "started"}


@router.post("/simulation/stop")
async def stop_simulation():
    """Stop the order generator."""
    if not _generator:
        raise HTTPException(503, "Generator not initialized")
    await _generator.stop()
    return {"status": "stopped", "total_generated": _generator.total_generated}


@router.get("/simulation/status")
async def simulation_status():
    """Get simulation status."""
    if not _generator:
        return {"status": "not_initialized"}
    return {
        "running": _generator.is_running,
        "total_generated": _generator.total_generated,
    }
