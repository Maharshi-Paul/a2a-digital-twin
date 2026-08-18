"""Order Coordinator Agent — Master Orchestrator.

Responsibilities:
- Ingests incoming order streams
- Maintains the master queue
- Delegates pick tasks to Picking Agent
- Monitors SLA deadlines and escalates at-risk orders
- Triggers queue re-scoring every cycle
- Logs dispatch-priority decisions to NegotiationTrace
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.a2a.message_bus import MessageBus
from core.a2a.protocol import A2AMessage, MessageType
from core.agents.base import BaseAgent
from domains.warehouse.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)


class OrderCoordinatorAgent(BaseAgent):
    """Master orchestrator that manages the order lifecycle."""

    def __init__(self, bus: MessageBus, session_factory: async_sessionmaker) -> None:
        super().__init__("order_coordinator", bus, session_factory)

    async def handle_message(self, msg: A2AMessage) -> None:
        """Route incoming messages to appropriate handlers."""
        match msg.msg_type:
            case MessageType.TASK_RESPONSE:
                await self._handle_task_response(msg)
            case MessageType.PICK_COMPLETE:
                await self._handle_pick_complete(msg)
            case MessageType.PACK_COMPLETE:
                await self._handle_pack_complete(msg)
            case MessageType.STOCKOUT_ALERT:
                await self._handle_stockout_escalation(msg)
            case MessageType.QUEUE_UPDATE:
                await self._handle_queue_update(msg)
            case MessageType.PICKER_UNAVAILABLE:
                await self._handle_picker_unavailable(msg)
            case MessageType.UNASSIGNED_TASKS_ALERT:
                await self._handle_unassigned_tasks(msg)
            case MessageType.PACKING_CAPACITY_UPDATE:
                await self._handle_packing_capacity(msg)
            case _:
                logger.debug("[order_coordinator] Unhandled msg_type: %s", msg.msg_type)

    # ── Order Ingestion ────────────────────────────────────────────────

    async def ingest_order(self, order_id: int) -> None:
        """Process a new order and dispatch pick tasks."""
        async with self.session_factory() as session:
            order = await session.get(Order, order_id)
            if not order:
                logger.warning("Order %d not found", order_id)
                return

            order.status = OrderStatus.QUEUED
            await session.commit()

            # Request stock check for order items
            await self.send(
                "inventory_agent",
                MessageType.STOCK_CHECK,
                payload={
                    "order_id": order.id,
                    "items": [
                        {"sku_id": item.sku_id, "quantity": item.quantity}
                        for item in order.items
                    ],
                },
            )
            logger.info("Order %d queued and stock check requested", order_id)

    # ── Dispatch Picking ───────────────────────────────────────────────

    async def dispatch_picking(self, order_id: int) -> None:
        """Send a pick assignment to the picking agent."""
        async with self.session_factory() as session:
            order = await session.get(Order, order_id)
            if not order:
                return
            order.status = OrderStatus.PICKING
            await session.commit()

        await self.send(
            "picking_agent",
            MessageType.PICK_ASSIGNMENT,
            payload={"order_id": order_id},
        )
        logger.info("Dispatched picking for order %d", order_id)

    # ── Response Handlers ──────────────────────────────────────────────

    async def _handle_task_response(self, msg: A2AMessage) -> None:
        """Handle generic task responses from agents."""
        logger.info(
            "[order_coordinator] Task response from %s: %s",
            msg.sender,
            msg.payload.get("status", "unknown"),
        )

    async def _handle_pick_complete(self, msg: A2AMessage) -> None:
        """Handle pick completion — route to packing."""
        order_id = msg.payload.get("order_id")
        if not order_id:
            return

        async with self.session_factory() as session:
            order = await session.get(Order, order_id)
            if order:
                order.status = OrderStatus.PICKED
                await session.commit()

        # Route to packing agent
        await self.send(
            "packing_agent",
            MessageType.PACK_REQUEST,
            payload={"order_id": order_id},
            correlation_id=msg.correlation_id,
        )
        logger.info("Order %d picked → routing to packing", order_id)

    async def _handle_pack_complete(self, msg: A2AMessage) -> None:
        """Handle pack completion — route to dispatch."""
        order_id = msg.payload.get("order_id")
        if not order_id:
            return

        async with self.session_factory() as session:
            order = await session.get(Order, order_id)
            if order:
                order.status = OrderStatus.PACKED
                await session.commit()

        # Route to dock agent for dispatch
        await self.send(
            "dock_agent",
            MessageType.DISPATCH_REQUEST,
            payload={"order_id": order_id},
            correlation_id=msg.correlation_id,
        )
        logger.info("Order %d packed → routing to dispatch", order_id)

    async def _handle_stockout_escalation(self, msg: A2AMessage) -> None:
        """Handle stockout alerts — log and await substitute resolution."""
        order_id = msg.payload.get("order_id")
        sku_id = msg.payload.get("sku_id")
        logger.warning(
            "[order_coordinator] STOCKOUT ESCALATION: order=%s sku=%s",
            order_id,
            sku_id,
        )

    async def _handle_queue_update(self, msg: A2AMessage) -> None:
        """Process queue re-scoring results and log dispatch-priority decisions."""
        t0 = time.monotonic()
        ranked_orders = msg.payload.get("ranked_order_ids", [])
        cycle = msg.payload.get("cycle", 0)
        top_score = msg.payload.get("top_score", 0.0)

        if ranked_orders:
            # Log the dispatch priority decision
            trace_id = await self._start_trace(
                order_id=ranked_orders[0] if ranked_orders else 0,
                trace_type="dispatch_priority",
                participants=["order_coordinator", "queue_engine"],
                metadata={"cycle": cycle},
            )

            await self._log_decision(
                trace_id=trace_id,
                step_number=1,
                action="update_priority_ranking",
                input_state={
                    "cycle": cycle,
                    "scored_count": msg.payload.get("scored_count", 0),
                },
                output={
                    "top_order_id": ranked_orders[0],
                    "top_score": top_score,
                    "ranked_order_ids": ranked_orders[:10],
                },
                latency_ms=self._ms_since(t0),
            )
            await self._complete_trace(trace_id, "resolved", self._ms_since(t0))

            logger.info(
                "[order_coordinator] Queue updated — top order: %s",
                ranked_orders[0],
            )

    async def _handle_picker_unavailable(self, msg: A2AMessage) -> None:
        """Handle picker unavailability — trigger task reassignment."""
        worker_id = msg.payload.get("worker_id")
        affected_orders = msg.payload.get("affected_order_ids", [])
        logger.warning(
            "[order_coordinator] Picker %s unavailable, %d orders affected",
            worker_id,
            len(affected_orders),
        )
        # Trigger reassignment for affected orders
        for order_id in affected_orders:
            await self.dispatch_picking(order_id)

    async def _handle_unassigned_tasks(self, msg: A2AMessage) -> None:
        """Handle unassigned tasks alert — recalculate priorities and reassign."""
        unassigned_ids = msg.payload.get("order_ids", [])
        logger.warning(
            "[order_coordinator] %d unassigned tasks detected — triggering reassignment",
            len(unassigned_ids),
        )
        for order_id in unassigned_ids:
            await self.dispatch_picking(order_id)

    async def _handle_packing_capacity(self, msg: A2AMessage) -> None:
        """Handle packing capacity update — adjust dispatch rate."""
        utilization = msg.payload.get("utilization", 0.0)
        logger.info(
            "[order_coordinator] Packing utilization update: %.1f%%",
            utilization * 100,
        )

    # ── SLA Monitor ────────────────────────────────────────────────────

    async def check_sla_risks(self) -> list[int]:
        """Identify orders at risk of SLA breach."""
        now = datetime.now(timezone.utc)
        at_risk = []
        async with self.session_factory() as session:
            stmt = select(Order).where(
                Order.status.in_([OrderStatus.PENDING, OrderStatus.QUEUED, OrderStatus.PICKING]),
                Order.sla_deadline <= now,
            )
            result = await session.execute(stmt)
            for order in result.scalars():
                at_risk.append(order.id)
                logger.warning("SLA BREACH RISK: order %d", order.id)
        return at_risk
