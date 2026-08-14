"""Base agent abstract class — all specialized agents inherit from this."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.a2a.bus import BROADCAST_CHANNEL, MessageBus
from app.a2a.handlers import persist_message
from app.a2a.protocol import A2AMessage, MessageType

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base for all warehouse digital twin agents.

    Provides:
    - Automatic Pub/Sub subscription to agent-specific and broadcast channels
    - Message sending helpers with optional persistence
    - Background task lifecycle management
    """

    def __init__(
        self,
        name: str,
        bus: MessageBus,
        session_factory: async_sessionmaker,
    ) -> None:
        self.name = name
        self.bus = bus
        self.session_factory = session_factory
        self._background_tasks: list[asyncio.Task] = []
        self._running = False

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Subscribe to channels and start background loops."""
        self._running = True
        channel = f"agent:{self.name}"
        await self.bus.subscribe(channel, self._on_message)
        await self.bus.subscribe(BROADCAST_CHANNEL, self._on_broadcast)
        logger.info("Agent [%s] started — listening on %s", self.name, channel)

    async def stop(self) -> None:
        """Cancel background tasks and mark as stopped."""
        self._running = False
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        logger.info("Agent [%s] stopped", self.name)

    def spawn_task(self, coro) -> asyncio.Task:
        """Spawn a tracked background task."""
        task = asyncio.create_task(coro, name=f"{self.name}_bg")
        self._background_tasks.append(task)
        return task

    # ── Message Handling ───────────────────────────────────────────────

    async def _on_message(self, msg: A2AMessage) -> None:
        """Handle a message directed to this agent."""
        if msg.receiver != self.name and msg.receiver != "*":
            return
        logger.info(
            "Agent [%s] received %s from %s",
            self.name, msg.msg_type.value, msg.sender,
        )
        # Persist for audit
        async with self.session_factory() as session:
            await persist_message(session, msg)
            await session.commit()
        await self.handle_message(msg)

    async def _on_broadcast(self, msg: A2AMessage) -> None:
        """Handle broadcast messages (skip own broadcasts)."""
        if msg.sender == self.name:
            return
        await self.handle_message(msg)

    @abstractmethod
    async def handle_message(self, msg: A2AMessage) -> None:
        """Process an incoming A2A message. Must be implemented by subclasses."""
        ...

    # ── Sending Helpers ────────────────────────────────────────────────

    async def send(
        self,
        target: str,
        msg_type: MessageType,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Send a message to a specific agent."""
        msg = A2AMessage(
            sender=self.name,
            receiver=target,
            msg_type=msg_type,
            payload=payload or {},
            correlation_id=correlation_id,
        )
        await self.bus.send_to_agent(target, msg)

    async def broadcast(
        self,
        msg_type: MessageType,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Broadcast a message to all agents."""
        msg = A2AMessage(
            sender=self.name,
            receiver="*",
            msg_type=msg_type,
            payload=payload or {},
        )
        await self.bus.broadcast(msg)

    async def reply(self, original: A2AMessage, msg_type: MessageType, payload: dict[str, Any] | None = None) -> None:
        """Reply to a message, preserving correlation_id."""
        reply_msg = original.reply(msg_type, payload)
        reply_msg.sender = self.name
        await self.bus.send_to_agent(original.sender, reply_msg)
