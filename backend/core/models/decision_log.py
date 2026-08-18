"""Decision logging models — NegotiationTrace and DecisionRecord.

Captures the full history of agent negotiation sequences so they can
be replayed, compared against a FIFO baseline, or analyzed for
algorithmic-vs-LLM performance differences.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base


class NegotiationTrace(Base):
    """A complete negotiation sequence between agents for one order.

    Each trace groups one or more ``DecisionRecord`` steps that together
    represent a single multi-agent negotiation (e.g. picking-assignment,
    dock-conflict-resolution, substitute-offer).
    """

    __tablename__ = "negotiation_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    trace_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # "picking_assignment", "dock_conflict", "substitute_offer", etc.
    initiated_by: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # agent name that started the negotiation
    participants: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )  # all agents involved
    outcome: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )  # "resolved", "escalated", "timed_out"
    decision_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="algorithmic"
    )  # "algorithmic", "llm", "fifo_baseline"
    duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    trace_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # full context snapshot
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return (
            f"<NegotiationTrace id={self.id} order={self.order_id} "
            f"type={self.trace_type!r} outcome={self.outcome!r}>"
        )


class DecisionRecord(Base):
    """Individual decision step within a negotiation trace.

    Captures the input state, action taken, reasoning (if LLM-driven),
    and output for each step in a negotiation.
    """

    __tablename__ = "decision_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )  # FK to negotiation_traces.id (soft reference to avoid cross-domain FK)
    agent_name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    action: Mapped[str] = mapped_column(
        String(128), nullable=False
    )  # "assign_worker", "select_dock", "accept_substitute", etc.
    input_state: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # state snapshot before decision
    reasoning: Mapped[str | None] = mapped_column(
        String(2000), nullable=True
    )  # LLM reasoning text, null for algorithmic
    output: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # decision result
    model_used: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # "claude-3-haiku", etc., null for algorithmic
    latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<DecisionRecord id={self.id} trace={self.trace_id} "
            f"agent={self.agent_name!r} action={self.action!r}>"
        )
