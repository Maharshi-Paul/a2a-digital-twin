"""Warehouse physical entities: Zone, Shelf, Worker, PackingStation, DockDoor."""

from __future__ import annotations

import enum

from sqlalchemy import (
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ── Enums ──────────────────────────────────────────────────────────────────────

class WorkerStatus(str, enum.Enum):
    IDLE = "IDLE"
    PICKING = "PICKING"
    TRAVELLING = "TRAVELLING"
    UNAVAILABLE = "UNAVAILABLE"


class StationStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class DockStatus(str, enum.Enum):
    FREE = "FREE"
    LOADING = "LOADING"
    OCCUPIED = "OCCUPIED"


# ── Zone ───────────────────────────────────────────────────────────────────────

class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    congestion_level: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )  # 0.0 (empty) → 1.0 (jammed)

    shelves = relationship("Shelf", back_populates="zone", lazy="selectin")
    workers = relationship("Worker", back_populates="current_zone", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Zone id={self.id} name={self.name!r} congestion={self.congestion_level:.2f}>"


# ── Shelf ──────────────────────────────────────────────────────────────────────

class Shelf(Base):
    __tablename__ = "shelves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zones.id"), nullable=False, index=True
    )
    aisle: Mapped[str] = mapped_column(String(10), nullable=False)
    rack: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    zone = relationship("Zone", back_populates="shelves")
    sku = relationship("SKU", back_populates="shelves")

    def __repr__(self) -> str:
        return (
            f"<Shelf id={self.id} aisle={self.aisle} rack={self.rack} "
            f"level={self.level} qty={self.quantity}>"
        )


# ── Worker ─────────────────────────────────────────────────────────────────────

class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[WorkerStatus] = mapped_column(
        Enum(WorkerStatus, name="worker_status"),
        nullable=False,
        default=WorkerStatus.IDLE,
    )
    current_zone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("zones.id"), nullable=True
    )
    task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    current_zone = relationship("Zone", back_populates="workers")
    orders = relationship("Order", back_populates="assigned_worker", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Worker id={self.id} name={self.name!r} status={self.status}>"


# ── Packing Station ───────────────────────────────────────────────────────────

class PackingStation(Base):
    __tablename__ = "packing_stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    current_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[StationStatus] = mapped_column(
        Enum(StationStatus, name="station_status"),
        nullable=False,
        default=StationStatus.AVAILABLE,
    )

    def __repr__(self) -> str:
        return f"<PackingStation id={self.id} load={self.current_load}/{self.capacity}>"


# ── Dock Door ─────────────────────────────────────────────────────────────────

class DockDoor(Base):
    __tablename__ = "dock_doors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[DockStatus] = mapped_column(
        Enum(DockStatus, name="dock_status"),
        nullable=False,
        default=DockStatus.FREE,
    )
    truck_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<DockDoor id={self.id} name={self.name!r} status={self.status}>"
