"""Core package — domain-agnostic framework components."""

from core.config import settings
from core.database import engine, async_session_factory, get_session
from core.models import Base, AgentMessage
from core.a2a import A2AMessage, MessageType, MessageBus, BROADCAST_CHANNEL
from core.agents import BaseAgent
from core.mcp import BaseMCPToolRegistry

__all__ = [
    "settings",
    "engine", "async_session_factory", "get_session",
    "Base", "AgentMessage",
    "A2AMessage", "MessageType", "MessageBus", "BROADCAST_CHANNEL",
    "BaseAgent",
    "BaseMCPToolRegistry",
]
