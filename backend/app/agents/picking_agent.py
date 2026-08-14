"""Picking Agent — worker assignment, path planning, and task management.

Responsibilities:
- Receives pick tasks from Order Coordinator
- Queries Inventory Agent for stock locations
- Assigns tasks to least-loaded worker in nearest zone
- Handles substitute offers from Inventory Agent
- Calculates shortest-path picking sequences
"""

from __future__ import annotations

import logging
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.a2a.bus import MessageBus
from app.a2a.protocol import A2AMessage, MessageType
from app.agents.base import BaseAgent
from app.models.order import Order, OrderItem, OrderStatus
from app.models.warehouse import Shelf, Worker, WorkerStatus

logger = logging.getLogger(__name__)


class PickingAgent(BaseAgent):
    """Manages picking task assignment and path optimization."""

    def __init__(self, bus: MessageBus, session_factory: async_sessionmaker) -> None:
        super().__init__("picking_agent", bus, session_factory)

    async def handle_message(self, msg: A2AMessage) -> None:
        match msg.msg_type:
            case MessageType.PICK_ASSIGNMENT:
                await self._handle_pick_assignment(msg)
            case MessageType.STOCK_RESPONSE:
                await self._handle_stock_response(msg)
            case MessageType.SUBSTITUTE_OFFER:
                await self._handle_substitute_offer(msg)
            case MessageType.NACK:
                await self._handle_nack(msg)
            case _:
                logger.debug("[picking] Unhandled: %s", msg.msg_type)

    # ── Pick Assignment ────────────────────────────────────────────────

    async def _handle_pick_assignment(self, msg: A2AMessage) -> None:
        """Receive a pick task — request stock locations from inventory."""
        order_id = msg.payload.get("order_id")
        logger.info("[picking] Received pick assignment for order %d", order_id)

        async with self.session_factory() as session:
            order = await session.get(Order, order_id)
            if not order:
                logger.warning("[picking] Order %d not found", order_id)
                return

            items = [
                {"sku_id": item.sku_id, "quantity": item.quantity}
                for item in order.items
                if not item.picked
            ]

        if items:
            await self.send(
                "inventory_agent",
                MessageType.STOCK_CHECK,
                payload={"order_id": order_id, "items": items},
                correlation_id=msg.id,
            )

    # ── Stock Response → Assign Worker ─────────────────────────────────

    async def _handle_stock_response(self, msg: A2AMessage) -> None:
        """Process stock availability and assign a worker."""
        order_id = msg.payload.get("order_id")
        items = msg.payload.get("items", [])
        all_available = msg.payload.get("all_available", False)

        if not all_available:
            logger.info(
                "[picking] Partial stock for order %d — waiting for substitutes",
                order_id,
            )
            return

        # Collect shelf locations for path planning
        shelf_locations = []
        for item in items:
            if item.get("available"):
                for loc in item.get("shelf_locations", []):
                    shelf_locations.append(loc)

        # Find best worker
        worker = await self._find_best_worker(shelf_locations)
        if not worker:
            logger.warning("[picking] No available workers for order %d", order_id)
            await self.send(
                "order_coordinator",
                MessageType.NACK,
                payload={"order_id": order_id, "reason": "no_workers_available"},
            )
            return

        # Assign worker
        async with self.session_factory() as session:
            order = await session.get(Order, order_id)
            if order:
                order.assigned_worker_id = worker["id"]
                order.status = OrderStatus.PICKING
                await session.commit()

            # Update worker status
            w = await session.get(Worker, worker["id"])
            if w:
                w.status = WorkerStatus.PICKING
                w.task_count += 1
                await session.commit()

        # Compute picking path
        path = self._compute_picking_path(shelf_locations)

        logger.info(
            "[picking] Assigned worker %d to order %d (path: %d stops)",
            worker["id"],
            order_id,
            len(path),
        )

        # Simulate pick completion (in production, this awaits IoT signals)
        await self._simulate_pick_completion(order_id, worker["id"])

    # ── Substitute Handling ────────────────────────────────────────────

    async def _handle_substitute_offer(self, msg: A2AMessage) -> None:
        """Accept the first available substitute SKU."""
        order_id = msg.payload.get("order_id")
        original_sku = msg.payload.get("original_sku_id")
        substitutes = msg.payload.get("substitutes", [])

        if not substitutes:
            logger.warning("[picking] No substitutes for SKU %d", original_sku)
            return

        # Accept the first substitute (highest availability)
        chosen = substitutes[0]
        logger.info(
            "[picking] Accepting substitute: SKU %d → %d for order %d",
            original_sku,
            chosen["sku_id"],
            order_id,
        )

        # Update order item with substitute
        async with self.session_factory() as session:
            stmt = select(OrderItem).where(
                OrderItem.order_id == order_id,
                OrderItem.sku_id == original_sku,
            )
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()
            if item:
                item.substituted_sku_id = chosen["sku_id"]
                await session.commit()

        # ACK the substitute
        await self.reply(
            msg,
            MessageType.ACK,
            payload={
                "order_id": order_id,
                "original_sku_id": original_sku,
                "accepted_sku_id": chosen["sku_id"],
            },
        )

        # Continue with picking using substitute
        await self.send(
            "inventory_agent",
            MessageType.STOCK_CHECK,
            payload={
                "order_id": order_id,
                "items": [{"sku_id": chosen["sku_id"], "quantity": 1}],
            },
        )

    async def _handle_nack(self, msg: A2AMessage) -> None:
        """Handle inability to fulfill — escalate to coordinator."""
        order_id = msg.payload.get("order_id")
        reason = msg.payload.get("reason", "unknown")
        logger.warning(
            "[picking] NACK for order %d: %s — escalating", order_id, reason
        )
        await self.send(
            "order_coordinator",
            MessageType.STOCKOUT_ALERT,
            payload={"order_id": order_id, "reason": reason},
        )

    # ── Worker Selection ───────────────────────────────────────────────

    async def _find_best_worker(
        self, shelf_locations: list[dict]
    ) -> dict | None:
        """Find the idle worker closest to the pick locations with lowest load."""
        async with self.session_factory() as session:
            stmt = select(Worker).where(Worker.status == WorkerStatus.IDLE)
            result = await session.execute(stmt)
            workers = list(result.scalars())

        if not workers:
            return None

        # Compute centroid of pick locations (approximate)
        if shelf_locations:
            avg_aisle = sum(ord(loc.get("aisle", "A")[0]) for loc in shelf_locations) / len(
                shelf_locations
            )
            avg_rack = sum(loc.get("rack", 1) for loc in shelf_locations) / len(
                shelf_locations
            )
        else:
            avg_aisle, avg_rack = 65.0, 1.0  # default 'A', rack 1

        # Score workers: prefer closest and least loaded
        best = None
        best_score = float("inf")
        for w in workers:
            dist = math.sqrt(
                (w.position_x - avg_aisle) ** 2 + (w.position_y - avg_rack) ** 2
            )
            score = dist + w.task_count * 5.0  # penalize heavily loaded workers
            if score < best_score:
                best_score = score
                best = {"id": w.id, "name": w.name, "score": score}

        return best

    # ── Path Planning ──────────────────────────────────────────────────

    def _compute_picking_path(self, locations: list[dict]) -> list[dict]:
        """Compute a greedy nearest-neighbor path through shelf locations.

        For MVP: uses simple distance-based greedy algorithm.
        Production would use OR-tools or similar TSP solver.
        """
        if not locations:
            return []

        remaining = list(locations)
        path = [remaining.pop(0)]

        while remaining:
            current = path[-1]
            cx = ord(current.get("aisle", "A")[0])
            cy = current.get("rack", 1)

            nearest_idx = 0
            nearest_dist = float("inf")
            for i, loc in enumerate(remaining):
                lx = ord(loc.get("aisle", "A")[0])
                ly = loc.get("rack", 1)
                d = abs(cx - lx) + abs(cy - ly)
                if d < nearest_dist:
                    nearest_dist = d
                    nearest_idx = i

            path.append(remaining.pop(nearest_idx))

        return path

    # ── Simulation ─────────────────────────────────────────────────────

    async def _simulate_pick_completion(self, order_id: int, worker_id: int) -> None:
        """Simulate pick completion after assignment."""
        import asyncio
        await asyncio.sleep(0.5)  # Simulate picking time

        async with self.session_factory() as session:
            order = await session.get(Order, order_id)
            if order:
                order.status = OrderStatus.PICKED
                for item in order.items:
                    item.picked = True
                await session.commit()

            worker = await session.get(Worker, worker_id)
            if worker:
                worker.status = WorkerStatus.IDLE
                await session.commit()

        # Notify coordinator
        await self.send(
            "order_coordinator",
            MessageType.PICK_COMPLETE,
            payload={"order_id": order_id, "worker_id": worker_id},
        )
        logger.info("[picking] Pick complete: order %d by worker %d", order_id, worker_id)
