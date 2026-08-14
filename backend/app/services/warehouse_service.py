"""Warehouse service — business logic layer for API routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func as sqlfunc, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_log import AgentMessage
from app.models.order import Order, OrderStatus
from app.models.warehouse import (
    DockDoor,
    PackingStation,
    Shelf,
    Worker,
    Zone,
)

logger = logging.getLogger(__name__)


class WarehouseService:
    """Encapsulates all warehouse data access logic."""

    @staticmethod
    async def get_orders(
        session: AsyncSession,
        status: OrderStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Fetch orders with optional status filter."""
        stmt = select(Order).order_by(desc(Order.priority_score))
        if status:
            stmt = stmt.where(Order.status == status)
        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return [
            {
                "id": o.id,
                "external_id": o.external_id,
                "status": o.status.value,
                "priority_score": round(o.priority_score, 4),
                "sla_deadline": o.sla_deadline.isoformat(),
                "assigned_worker_id": o.assigned_worker_id,
                "item_count": len(o.items),
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in result.scalars()
        ]

    @staticmethod
    async def get_order_count(session: AsyncSession) -> dict:
        """Get order counts by status."""
        stmt = (
            select(Order.status, sqlfunc.count(Order.id))
            .group_by(Order.status)
        )
        result = await session.execute(stmt)
        counts = {row[0].value: row[1] for row in result.fetchall()}
        total = sum(counts.values())
        return {"total": total, "by_status": counts}

    @staticmethod
    async def get_warehouse_status(session: AsyncSession) -> dict:
        """Get comprehensive warehouse status snapshot."""
        # Zones
        zones_result = await session.execute(select(Zone))
        zones = [
            {
                "id": z.id,
                "name": z.name,
                "congestion": round(z.congestion_level, 2),
            }
            for z in zones_result.scalars()
        ]

        # Workers
        workers_result = await session.execute(select(Worker))
        workers = [
            {
                "id": w.id,
                "name": w.name,
                "status": w.status.value,
                "zone_id": w.current_zone_id,
                "tasks": w.task_count,
                "pos": [w.position_x, w.position_y],
            }
            for w in workers_result.scalars()
        ]

        # Packing
        packing_result = await session.execute(select(PackingStation))
        packing = [
            {
                "id": ps.id,
                "name": ps.name,
                "load": ps.current_load,
                "capacity": ps.capacity,
                "status": ps.status.value,
            }
            for ps in packing_result.scalars()
        ]

        # Docks
        dock_result = await session.execute(select(DockDoor))
        docks = [
            {
                "id": d.id,
                "name": d.name,
                "status": d.status.value,
                "truck": d.truck_id,
            }
            for d in dock_result.scalars()
        ]

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "zones": zones,
            "workers": workers,
            "packing_stations": packing,
            "dock_doors": docks,
        }

    @staticmethod
    async def get_agent_logs(
        session: AsyncSession, limit: int = 50
    ) -> list[dict]:
        """Fetch recent agent communication logs."""
        stmt = (
            select(AgentMessage)
            .order_by(desc(AgentMessage.timestamp))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [
            {
                "id": m.id,
                "sender": m.sender,
                "receiver": m.receiver,
                "type": m.msg_type,
                "correlation_id": m.correlation_id,
                "payload": m.payload,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            }
            for m in result.scalars()
        ]

    @staticmethod
    async def get_kpis(session: AsyncSession) -> dict:
        """Compute real-time KPIs for the dashboard."""
        now = datetime.now(timezone.utc)

        # Order throughput
        order_counts = await WarehouseService.get_order_count(session)

        # Average priority score
        stmt = select(sqlfunc.avg(Order.priority_score)).where(
            Order.status.in_([OrderStatus.PENDING, OrderStatus.QUEUED])
        )
        result = await session.execute(stmt)
        avg_priority = result.scalar() or 0.0

        # SLA compliance
        breached_stmt = select(sqlfunc.count(Order.id)).where(
            Order.sla_deadline < now,
            Order.status.in_([
                OrderStatus.PENDING,
                OrderStatus.QUEUED,
                OrderStatus.PICKING,
            ]),
        )
        breached_result = await session.execute(breached_stmt)
        sla_breached = breached_result.scalar() or 0

        # Worker utilization
        total_workers_stmt = select(sqlfunc.count(Worker.id))
        busy_workers_stmt = select(sqlfunc.count(Worker.id)).where(
            Worker.status != "IDLE"
        )
        total_w = (await session.execute(total_workers_stmt)).scalar() or 1
        busy_w = (await session.execute(busy_workers_stmt)).scalar() or 0

        # Avg congestion
        avg_cong_stmt = select(sqlfunc.avg(Zone.congestion_level))
        avg_congestion = (await session.execute(avg_cong_stmt)).scalar() or 0.0

        return {
            "timestamp": now.isoformat(),
            "orders": order_counts,
            "avg_priority_score": round(float(avg_priority), 4),
            "sla_breached_count": sla_breached,
            "worker_utilization": round(busy_w / total_w, 2),
            "avg_zone_congestion": round(float(avg_congestion), 2),
        }
