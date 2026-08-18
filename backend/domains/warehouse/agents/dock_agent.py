"""Dock Agent — manages dock doors, truck queues, and dispatch coordination.

Responsibilities:
- Manages inbound/outbound dock door queues
- Coordinates truck loading and dispatch timing
- Reports dispatch readiness to Order Coordinator
- Logs dock-assignment decisions to NegotiationTrace
- (Hybrid mode) Uses LLM for conflict resolution when multiple orders
  compete for limited dock doors
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.a2a.message_bus import MessageBus
from core.a2a.protocol import A2AMessage, MessageType
from core.agents.base import BaseAgent
from domains.warehouse.models.order import Order, OrderStatus
from domains.warehouse.models.warehouse import DockDoor, DockStatus

logger = logging.getLogger(__name__)


class DockAgent(BaseAgent):
    """Manages dock doors and dispatch operations.

    In hybrid decision mode, this agent is the designated LLM-powered
    agent.  When dock contention occurs (dispatch queue depth > 0),
    the agent can optionally call the Anthropic API via MCP tools for
    conflict-resolution reasoning.
    """

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
        t0 = time.monotonic()
        order_id = msg.payload.get("order_id")
        if not order_id:
            return

        # Start decision trace
        trace_id = await self._start_trace(
            order_id=order_id,
            trace_type="dock_assignment",
            participants=["dock_agent", "order_coordinator"],
            decision_method="algorithmic",
            metadata={"queue_depth": len(self._dispatch_queue)},
        )

        door, all_doors = await self._find_free_door()
        if not door:
            # Queue the dispatch — potential conflict zone
            self._dispatch_queue.append(order_id)

            await self._log_decision(
                trace_id=trace_id,
                step_number=1,
                action="queue_dispatch",
                input_state={
                    "order_id": order_id,
                    "doors": all_doors,
                    "queue_depth_before": len(self._dispatch_queue) - 1,
                },
                output={
                    "result": "queued",
                    "queue_depth_after": len(self._dispatch_queue),
                    "queue_position": len(self._dispatch_queue),
                },
                latency_ms=self._ms_since(t0),
            )
            await self._complete_trace(trace_id, "resolved", self._ms_since(t0))

            logger.info(
                "[dock] No free doors — queued order %d (queue depth: %d)",
                order_id,
                len(self._dispatch_queue),
            )
            return

        # Log the dock assignment decision
        await self._log_decision(
            trace_id=trace_id,
            step_number=1,
            action="assign_dock",
            input_state={
                "order_id": order_id,
                "doors": all_doors,
                "queue_depth": len(self._dispatch_queue),
            },
            output={
                "selected_door_id": door["id"],
                "selected_door_name": door["name"],
            },
            latency_ms=self._ms_since(t0),
        )
        await self._complete_trace(trace_id, "resolved", self._ms_since(t0))

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

    async def _find_free_door(self) -> tuple[dict | None, list[dict]]:
        """Find a free dock door.

        Returns:
            Tuple of (free_door_dict_or_None, list_of_all_door_dicts).
        """
        async with self.session_factory() as session:
            result = await session.execute(select(DockDoor))
            all_doors_orm = list(result.scalars())

        all_doors = [
            {
                "id": d.id,
                "name": d.name,
                "status": d.status.value,
                "truck_id": d.truck_id,
            }
            for d in all_doors_orm
        ]

        free = [d for d in all_doors if d["status"] == DockStatus.FREE.value]
        if free:
            return free[0], all_doors
        return None, all_doors

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
