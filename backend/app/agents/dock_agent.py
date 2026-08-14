"""Dock Agent — manages dock doors, truck queues, and dispatch coordination.

Responsibilities:
- Manages inbound/outbound dock door queues
- Coordinates truck loading and dispatch timing
- Reports dispatch readiness to Order Coordinator
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.a2a.bus import MessageBus
from app.a2a.protocol import A2AMessage, MessageType
from app.agents.base import BaseAgent
from app.models.order import Order, OrderStatus
from app.models.warehouse import DockDoor, DockStatus

logger = logging.getLogger(__name__)


class DockAgent(BaseAgent):
    """Manages dock doors and dispatch operations."""

    def __init__(self, bus: MessageBus, session_factory: async_sessionmaker) -> None:
        super().__init__("dock_agent", bus, session_factory)
        self._dispatch_queue: list[int] = []

    async def handle_message(self, msg: A2AMessage) -> None:
        match msg.msg_type:
            case MessageType.DISPATCH_REQUEST:
                await self._handle_dispatch_request(msg)
            case _:
                logger.debug("[dock] Unhandled: %s", msg.msg_type)

    async def _handle_dispatch_request(self, msg: A2AMessage) -> None:
        """Handle a dispatch request — assign to available dock door."""
        order_id = msg.payload.get("order_id")
        if not order_id:
            return

        door = await self._find_free_door()
        if not door:
            # Queue the dispatch
            self._dispatch_queue.append(order_id)
            logger.info(
                "[dock] No free doors — queued order %d (queue depth: %d)",
                order_id,
                len(self._dispatch_queue),
            )
            return

        # Assign door
        async with self.session_factory() as session:
            d = await session.get(DockDoor, door["id"])
            if d:
                d.status = DockStatus.LOADING
                d.truck_id = f"TRUCK-{order_id}"
                await session.commit()

            order = await session.get(Order, order_id)
            if order:
                order.status = OrderStatus.DISPATCHED
                await session.commit()

        logger.info(
            "[dock] Order %d dispatched via dock %s", order_id, door["name"]
        )

        # Simulate loading
        import asyncio
        await asyncio.sleep(0.2)

        # Free the door
        async with self.session_factory() as session:
            d = await session.get(DockDoor, door["id"])
            if d:
                d.status = DockStatus.FREE
                d.truck_id = None
                await session.commit()

        # Broadcast dispatch event
        await self.broadcast(
            MessageType.DISPATCH_READY,
            payload={"order_id": order_id, "dock_door": door["name"]},
        )

        # Process queued dispatches
        if self._dispatch_queue:
            next_order = self._dispatch_queue.pop(0)
            await self._handle_dispatch_request(
                A2AMessage(
                    sender=self.name,
                    receiver=self.name,
                    msg_type=MessageType.DISPATCH_REQUEST,
                    payload={"order_id": next_order},
                )
            )

    async def _find_free_door(self) -> dict | None:
        """Find a free dock door."""
        async with self.session_factory() as session:
            stmt = select(DockDoor).where(DockDoor.status == DockStatus.FREE)
            result = await session.execute(stmt)
            door = result.scalar_one_or_none()
            if door:
                return {"id": door.id, "name": door.name}
        return None

    async def get_dock_status(self) -> dict:
        """Get current status of all dock doors."""
        async with self.session_factory() as session:
            stmt = select(DockDoor)
            result = await session.execute(stmt)
            doors = list(result.scalars())
        return {
            "doors": [
                {
                    "id": d.id,
                    "name": d.name,
                    "status": d.status.value,
                    "truck_id": d.truck_id,
                }
                for d in doors
            ],
            "queue_depth": len(self._dispatch_queue),
        }
