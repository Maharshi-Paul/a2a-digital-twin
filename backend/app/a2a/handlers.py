"""A2A message routing and persistent logging handler."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.a2a.protocol import A2AMessage
from app.models.agent_log import AgentMessage

logger = logging.getLogger(__name__)


async def persist_message(session: AsyncSession, msg: A2AMessage) -> None:
    """Write an A2A message to the database for audit trail."""
    record = AgentMessage(
        sender=msg.sender,
        receiver=msg.receiver,
        msg_type=msg.msg_type.value,
        correlation_id=msg.correlation_id,
        payload=msg.payload,
    )
    session.add(record)
    await session.flush()
    logger.debug("Persisted A2A message %s → %s [%s]", msg.sender, msg.receiver, msg.msg_type)
