"""Packing Agent — packing station management and optimal routing.

Responsibilities:
- Monitors packing station capacities
- Routes completed picks to optimal packing stations
- Reports pack completion to Order Coordinator
- Broadcasts capacity updates
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.a2a.message_bus import MessageBus
from core.a2a.protocol import A2AMessage, MessageType
from core.agents.base import BaseAgent
from domains.warehouse.models.order import Order, OrderStatus
from domains.warehouse.models.warehouse import PackingStation, StationStatus

logger = logging.getLogger(__name__)


class PackingAgent(BaseAgent):
    """Manages packing station routing and capacity."""

    def __init__(self, bus: MessageBus, session_factory: async_sessionmaker) -> None:
        super().__init__("packing_agent", bus, session_factory)

    async def handle_message(self, msg: A2AMessage) -> None:
        match msg.msg_type:
            case MessageType.PACK_REQUEST:
                await self._handle_pack_request(msg)
            case _:
                logger.debug("[packing] Unhandled: %s", msg.msg_type)

    async def _handle_pack_request(self, msg: A2AMessage) -> None:
        """Route a picked order to the best packing station."""
        order_id = msg.payload.get("order_id")
        if not order_id:
            return

        station = await self._find_best_station()
        if not station:
            logger.warning("[packing] No available packing stations!")
            await self.reply(
                msg,
                MessageType.NACK,
                payload={"order_id": order_id, "reason": "no_packing_capacity"},
            )
            return

        # Assign to station
        async with self.session_factory() as session:
            order = await session.get(Order, order_id)
            if order:
                order.status = OrderStatus.PACKING
                await session.commit()

            ps = await session.get(PackingStation, station["id"])
            if ps:
                ps.current_load += 1
                if ps.current_load >= ps.capacity:
                    ps.status = StationStatus.BUSY
                await session.commit()

        logger.info(
            "[packing] Order %d → station %s (load: %d/%d)",
            order_id,
            station["name"],
            station["current_load"] + 1,
            station["capacity"],
        )

        # Broadcast capacity update to coordinator
        utilization = await self.get_packing_utilization()
        await self.send(
            "order_coordinator",
            MessageType.PACKING_CAPACITY_UPDATE,
            payload={"utilization": utilization},
        )

        # Simulate packing time
        await asyncio.sleep(0.3)

        # Release station capacity
        async with self.session_factory() as session:
            ps = await session.get(PackingStation, station["id"])
            if ps:
                ps.current_load = max(0, ps.current_load - 1)
                if ps.current_load < ps.capacity:
                    ps.status = StationStatus.AVAILABLE
                await session.commit()

        # Report completion
        await self.send(
            "order_coordinator",
            MessageType.PACK_COMPLETE,
            payload={
                "order_id": order_id,
                "station_id": station["id"],
            },
            correlation_id=msg.correlation_id,
        )
        logger.info("[packing] Pack complete: order %d at station %s", order_id, station["name"])

    async def _find_best_station(self) -> dict | None:
        """Find the packing station with the most available capacity."""
        async with self.session_factory() as session:
            stmt = (
                select(PackingStation)
                .where(PackingStation.status == StationStatus.AVAILABLE)
                .order_by((PackingStation.capacity - PackingStation.current_load).desc())
            )
            result = await session.execute(stmt)
            station = result.scalar_one_or_none()

            if station:
                return {
                    "id": station.id,
                    "name": station.name,
                    "capacity": station.capacity,
                    "current_load": station.current_load,
                }
        return None

    async def get_packing_utilization(self) -> float:
        """Get overall packing utilization (0.0 to 1.0)."""
        async with self.session_factory() as session:
            stmt = select(PackingStation)
            result = await session.execute(stmt)
            stations = list(result.scalars())

        if not stations:
            return 0.0

        total_capacity = sum(s.capacity for s in stations)
        total_load = sum(s.current_load for s in stations)
        return total_load / total_capacity if total_capacity > 0 else 1.0
