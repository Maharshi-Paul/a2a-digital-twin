"""SKU (Stock Keeping Unit) model."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base


class SKU(Base):
    __tablename__ = "skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    substitute_sku_ids: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer), nullable=True, default=list
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    shelves = relationship("Shelf", back_populates="sku", lazy="selectin")
    order_items = relationship("OrderItem", back_populates="sku", lazy="selectin")

    def __repr__(self) -> str:
        return f"<SKU id={self.id} name={self.name!r}>"
