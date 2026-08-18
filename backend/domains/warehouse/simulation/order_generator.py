"""Poisson-distributed order generator for warehouse simulation.

Generates synthetic orders at a configurable rate (λ orders/min)
using a Poisson process.  Now driven by ``ArrivalRateConfig`` from
the core simulation framework.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.simulation.config import ArrivalRateConfig
from domains.warehouse.models.inventory_item import SKU
from domains.warehouse.models.order import Order, OrderItem, OrderStatus

logger = logging.getLogger(__name__)


class OrderGenerator:
    """Generates synthetic orders following a Poisson process."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        on_order_created: asyncio.coroutines | None = None,
        arrival_config: ArrivalRateConfig | None = None,
        *,
        lam: float | None = None,
    ) -> None:
        # Support both new config and legacy ``lam`` kwarg
        if arrival_config is not None:
            self._config = arrival_config
        else:
            from core.config import settings
            self._config = ArrivalRateConfig(
                lambda_per_minute=lam if lam is not None else settings.simulation_lambda,
            )

        self.session_factory = session_factory
        self.on_order_created = on_order_created
        self._task: asyncio.Task | None = None
        self._running = False
        self._total_generated = 0
        self._sku_ids: list[int] = []

    @property
    def lam(self) -> float:
        """Current λ (orders/minute) for backward compatibility."""
        return self._config.lambda_per_minute

    # ── Lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Start generating orders."""
        self._running = True

        # Cache SKU IDs
        async with self.session_factory() as session:
            result = await session.execute(select(SKU.id))
            self._sku_ids = [row[0] for row in result.fetchall()]

        if not self._sku_ids:
            logger.warning("No SKUs found — cannot generate orders")
            return

        self._task = asyncio.create_task(self._generate_loop(), name="order_generator")
        logger.info(
            "Order Generator started (λ=%.1f orders/min, %d SKUs available, "
            "SLA=%d–%dmin, items=%d–%d)",
            self._config.lambda_per_minute,
            len(self._sku_ids),
            self._config.sla_window_minutes[0],
            self._config.sla_window_minutes[1],
            self._config.items_per_event[0],
            self._config.items_per_event[1],
        )

    async def stop(self) -> None:
        """Stop generating orders."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(
            "Order Generator stopped. Total generated: %d", self._total_generated
        )

    # ── Generator Loop ─────────────────────────────────────────────

    async def _generate_loop(self) -> None:
        """Poisson-process order generation loop."""
        while self._running:
            try:
                # Poisson inter-arrival time (exponential distribution)
                rate_per_second = self._config.lambda_per_minute / 60.0
                interval = random.expovariate(rate_per_second)

                # Cap interval to prevent long waits
                interval = min(interval, self._config.max_interval_seconds)
                await asyncio.sleep(interval)

                order = await self._create_order()
                if order and self.on_order_created:
                    await self.on_order_created(order.id)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error generating order")
                await asyncio.sleep(1.0)

    async def _create_order(self) -> Order | None:
        """Create a single random order with configurable item count."""
        now = datetime.now(timezone.utc)

        item_min, item_max = self._config.items_per_event
        num_items = random.randint(item_min, item_max)
        chosen_skus = random.sample(
            self._sku_ids, min(num_items, len(self._sku_ids))
        )

        # SLA deadline from config range
        sla_min, sla_max = self._config.sla_window_minutes
        sla_minutes = random.randint(sla_min, sla_max)
        sla_deadline = now + timedelta(minutes=sla_minutes)

        external_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

        async with self.session_factory() as session:
            order = Order(
                external_id=external_id,
                status=OrderStatus.PENDING,
                sla_deadline=sla_deadline,
                priority_score=0.0,
            )
            session.add(order)
            await session.flush()

            for sku_id in chosen_skus:
                item = OrderItem(
                    order_id=order.id,
                    sku_id=sku_id,
                    quantity=random.randint(1, 3),
                    picked=False,
                )
                session.add(item)

            await session.commit()
            await session.refresh(order)

            self._total_generated += 1
            logger.info(
                "Generated order %s (items=%d, SLA=%dm, total=%d)",
                external_id,
                len(chosen_skus),
                sla_minutes,
                self._total_generated,
            )
            return order

    # ── Public API ─────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def total_generated(self) -> int:
        return self._total_generated

    @property
    def config(self) -> ArrivalRateConfig:
        """Expose the arrival-rate config for API introspection."""
        return self._config
