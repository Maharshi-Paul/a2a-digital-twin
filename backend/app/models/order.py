"""Order and OrderItem models."""

from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PICKING = "PICKING"
    PICKED = "PICKED"
    PACKING = "PACKING"
    PACKED = "PACKED"
    DISPATCHED = "DISPATCHED"
    CANCELLED = "CANCELLED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        nullable=False,
        default=OrderStatus.PENDING,
        index=True,
    )
    sla_deadline: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    priority_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, index=True
    )
    assigned_worker_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workers.id"), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    items = relationship(
        "OrderItem", back_populates="order", lazy="selectin", cascade="all, delete-orphan"
    )
    assigned_worker = relationship("Worker", back_populates="orders", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Order id={self.id} ext={self.external_id!r} status={self.status}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    picked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    substituted_sku_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="items")
    sku = relationship("SKU", back_populates="order_items", lazy="selectin")

    def __repr__(self) -> str:
        return f"<OrderItem id={self.id} sku={self.sku_id} qty={self.quantity}>"
