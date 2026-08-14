"""A2A protocol message envelope and type definitions."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, enum.Enum):
    """Supported A2A message types."""
    TASK_REQUEST = "TASK_REQUEST"
    TASK_RESPONSE = "TASK_RESPONSE"
    STOCK_CHECK = "STOCK_CHECK"
    STOCK_RESPONSE = "STOCK_RESPONSE"
    STOCKOUT_ALERT = "STOCKOUT_ALERT"
    SUBSTITUTE_OFFER = "SUBSTITUTE_OFFER"
    PICK_ASSIGNMENT = "PICK_ASSIGNMENT"
    PICK_COMPLETE = "PICK_COMPLETE"
    PACK_REQUEST = "PACK_REQUEST"
    PACK_COMPLETE = "PACK_COMPLETE"
    DISPATCH_REQUEST = "DISPATCH_REQUEST"
    DISPATCH_READY = "DISPATCH_READY"
    QUEUE_UPDATE = "QUEUE_UPDATE"
    WORKER_STATUS = "WORKER_STATUS"
    ACK = "ACK"
    NACK = "NACK"
    HEARTBEAT = "HEARTBEAT"


class A2AMessage(BaseModel):
    """Standardized agent-to-agent message envelope."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    sender: str
    receiver: str
    msg_type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 30

    def reply(
        self,
        msg_type: MessageType,
        payload: dict[str, Any] | None = None,
    ) -> "A2AMessage":
        """Create a reply message with preserved correlation_id."""
        return A2AMessage(
            sender=self.receiver,
            receiver=self.sender,
            msg_type=msg_type,
            payload=payload or {},
            correlation_id=self.correlation_id or self.id,
        )
