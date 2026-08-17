"""Base queue engine — domain-agnostic priority queue loop.

Subclasses implement _tick() with domain-specific scoring logic.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.a2a.message_bus import MessageBus

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BaseScoredOrder:
    """Base result from scoring an order."""
    order_id: int
    external_id: str
    total_score: float


class BaseQueueEngine(ABC):
    """Abstract base for domain-specific queue engines."""

    def __init__(
        self,
        bus: MessageBus,
        tick_seconds: float = 2.0,
    ) -> None:
        self.bus = bus
        self.tick_seconds = tick_seconds
        self._task: asyncio.Task | None = None
        self._running = False
        self._cycle_count = 0

    async def start(self) -> None:
        """Start the queue engine loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="queue_engine")
        logger.info("Queue Engine started (tick=%.1fs)", self.tick_seconds)

    async def stop(self) -> None:
        """Stop the queue engine loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Queue Engine stopped after %d cycles", self._cycle_count)

    async def _run_loop(self) -> None:
        """Core loop — calls _tick every cycle."""
        while self._running:
            try:
                await self._tick()
                self._cycle_count += 1
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Queue engine tick failed")
            await asyncio.sleep(self.tick_seconds)

    @abstractmethod
    async def _tick(self) -> None:
        """Execute a single scoring cycle. Implemented by domain engines."""
        ...

    @property
    def cycle_count(self) -> int:
        return self._cycle_count
