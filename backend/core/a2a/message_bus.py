"""Redis Pub/Sub-based A2A message bus for inter-agent communication.

High-performance async message bus using redis.asyncio with orjson
serialization. Each agent subscribes to its own channel and broadcasts
are supported via a shared channel.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import orjson
import redis.asyncio as aioredis

from core.a2a.protocol import A2AMessage

logger = logging.getLogger(__name__)

HandlerFunc = Callable[[A2AMessage], Coroutine[Any, Any, None]]

BROADCAST_CHANNEL = "agent:broadcast"


class MessageBus:
    """Centralized Redis Pub/Sub message bus for A2A communication."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._handlers: dict[str, list[HandlerFunc]] = {}
        self._listener_task: asyncio.Task | None = None
        self._running = False
        self._message_count = 0

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Establish Redis connection and Pub/Sub client."""
        self._redis = aioredis.from_url(
            self._redis_url,
            decode_responses=False,
            max_connections=50,
        )
        self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        logger.info("MessageBus connected to Redis at %s", self._redis_url)

    async def disconnect(self) -> None:
        """Gracefully shut down listener and close connections."""
        self._running = False
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        logger.info(
            "MessageBus disconnected. Total messages processed: %d",
            self._message_count,
        )

    # ── Subscribe / Publish ────────────────────────────────────────────

    async def subscribe(self, channel: str, handler: HandlerFunc) -> None:
        """Subscribe a handler to a specific channel."""
        if channel not in self._handlers:
            self._handlers[channel] = []
            if self._pubsub:
                await self._pubsub.subscribe(channel)
        self._handlers[channel].append(handler)
        logger.debug("Subscribed handler to channel: %s", channel)

    async def publish(self, channel: str, message: A2AMessage) -> int:
        """Publish a message to a channel. Returns subscriber count."""
        if not self._redis:
            raise RuntimeError("MessageBus not connected")
        data = orjson.dumps(message.model_dump(mode="json"))
        count = await self._redis.publish(channel, data)
        self._message_count += 1
        logger.debug(
            "Published %s → %s [%s] (subscribers=%d)",
            message.sender,
            channel,
            message.msg_type.value,
            count,
        )
        return count

    async def send_to_agent(self, agent_name: str, message: A2AMessage) -> int:
        """Send a message to a specific agent's channel."""
        return await self.publish(f"agent:{agent_name}", message)

    async def broadcast(self, message: A2AMessage) -> int:
        """Broadcast a message to all listeners on the broadcast channel."""
        return await self.publish(BROADCAST_CHANNEL, message)

    # ── Listener Loop ──────────────────────────────────────────────────

    async def start_listening(self) -> None:
        """Start the background listener task."""
        self._running = True
        self._listener_task = asyncio.create_task(
            self._listen_loop(), name="message_bus_listener"
        )
        logger.info("MessageBus listener started")

    async def _listen_loop(self) -> None:
        """Core listener loop — dispatches messages to registered handlers."""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.1
                )
                if message and message["type"] == "message":
                    channel = (
                        message["channel"].decode()
                        if isinstance(message["channel"], bytes)
                        else message["channel"]
                    )
                    data = orjson.loads(message["data"])
                    a2a_msg = A2AMessage(**data)
                    await self._dispatch(channel, a2a_msg)
                else:
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in message bus listener")
                await asyncio.sleep(0.5)

    async def _dispatch(self, channel: str, message: A2AMessage) -> None:
        """Dispatch message to all handlers registered on the channel."""
        handlers = self._handlers.get(channel, [])
        if not handlers:
            logger.warning("No handlers for channel %s", channel)
            return
        tasks = [asyncio.create_task(h(message)) for h in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Handler %d on channel %s failed: %s",
                    i,
                    channel,
                    result,
                )

    # ── Sorted-Set Queue Helpers ───────────────────────────────────────

    async def update_priority_queue(
        self, queue_key: str, order_scores: dict[str, float]
    ) -> None:
        """Atomically update a Redis sorted set with order priority scores."""
        if not self._redis or not order_scores:
            return
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.delete(queue_key)
            pipe.zadd(queue_key, order_scores)
            await pipe.execute()

    async def get_top_orders(
        self, queue_key: str, count: int = 50
    ) -> list[tuple[str, float]]:
        """Retrieve top-N orders by priority score (highest first)."""
        if not self._redis:
            return []
        results = await self._redis.zrevrange(
            queue_key, 0, count - 1, withscores=True
        )
        return [
            (
                member.decode() if isinstance(member, bytes) else member,
                score,
            )
            for member, score in results
        ]

    # ── Redis Direct Access ────────────────────────────────────────────

    async def set_state(self, key: str, value: bytes | str, ex: int | None = None) -> None:
        """Set a key in Redis for state caching."""
        if self._redis:
            await self._redis.set(key, value, ex=ex)

    async def get_state(self, key: str) -> bytes | None:
        """Get a key from Redis."""
        if self._redis:
            return await self._redis.get(key)
        return None

    @property
    def message_count(self) -> int:
        return self._message_count
