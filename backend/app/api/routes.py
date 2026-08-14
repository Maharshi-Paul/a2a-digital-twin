"""REST API routes for the Warehouse Digital Twin."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.order import OrderStatus
from app.services.warehouse_service import WarehouseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Warehouse API"])

_service = WarehouseService()

# References set at startup
_simulation_generator = None
_order_coordinator = None
_queue_engine = None


def set_refs(generator, coordinator, queue_engine) -> None:
    global _simulation_generator, _order_coordinator, _queue_engine
    _simulation_generator = generator
    _order_coordinator = coordinator
    _queue_engine = queue_engine


# ── Orders ───────────────────────────────────────────────────────

@router.get("/orders")
async def list_orders(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated order list sorted by priority score."""
    order_status = OrderStatus(status) if status else None
    orders = await _service.get_orders(session, order_status, limit, offset)
    counts = await _service.get_order_count(session)
    return {"orders": orders, "counts": counts}


@router.get("/orders/count")
async def order_counts(session: AsyncSession = Depends(get_session)):
    """Get order counts by status."""
    return await _service.get_order_count(session)


# ── Queue ────────────────────────────────────────────────────────

@router.get("/queue")
async def get_queue():
    """Get current priority queue ranking."""
    if not _queue_engine:
        return {"queue": [], "cycle": 0}
    scored = _queue_engine.get_last_scored()
    return {
        "queue": [
            {
                "order_id": s.order_id,
                "external_id": s.external_id,
                "total_score": s.total_score,
                "sla_risk": s.sla_risk,
                "wait_time": s.wait_time_norm,
                "inventory_readiness": s.inventory_readiness,
                "congestion_inv": s.congestion_inv,
                "packing_capacity": s.packing_capacity,
            }
            for s in scored
        ],
        "cycle": _queue_engine.cycle_count,
    }


# ── Warehouse Status ─────────────────────────────────────────────

@router.get("/warehouse/status")
async def warehouse_status(session: AsyncSession = Depends(get_session)):
    """Get comprehensive warehouse status snapshot."""
    return await _service.get_warehouse_status(session)


@router.get("/warehouse/kpis")
async def warehouse_kpis(session: AsyncSession = Depends(get_session)):
    """Get real-time warehouse KPIs."""
    return await _service.get_kpis(session)


# ── Agent Logs ───────────────────────────────────────────────────

@router.get("/agents/logs")
async def agent_logs(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get recent agent-to-agent communication logs."""
    logs = await _service.get_agent_logs(session, limit)
    return {"logs": logs, "count": len(logs)}


# ── Simulation Control ───────────────────────────────────────────

@router.post("/simulation/seed")
async def seed_simulation(session: AsyncSession = Depends(get_session)):
    """Seed the database with simulated warehouse data."""
    from app.simulation.seeder import seed_database

    result = await seed_database(session)
    return {"status": "seeded", "counts": result}


@router.post("/simulation/start")
async def start_simulation():
    """Start the Poisson order generator."""
    if not _simulation_generator:
        return {"status": "error", "message": "Generator not initialized"}
    if _simulation_generator.is_running:
        return {"status": "already_running"}
    await _simulation_generator.start()
    return {"status": "started", "lambda": _simulation_generator.lam}


@router.post("/simulation/stop")
async def stop_simulation():
    """Stop the order generator."""
    if not _simulation_generator:
        return {"status": "error", "message": "Generator not initialized"}
    if not _simulation_generator.is_running:
        return {"status": "already_stopped"}
    await _simulation_generator.stop()
    return {
        "status": "stopped",
        "total_generated": _simulation_generator.total_generated,
    }


@router.get("/simulation/status")
async def simulation_status():
    """Get simulation status."""
    if not _simulation_generator:
        return {"running": False, "total_generated": 0}
    return {
        "running": _simulation_generator.is_running,
        "total_generated": _simulation_generator.total_generated,
    }
