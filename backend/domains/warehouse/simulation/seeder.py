"""Warehouse database seeder — config-driven entity creation.

Uses the core SimulationEngine factory-registry pattern.  Each entity type
(zone, sku, shelf, worker, packing_station, dock_door) has its own factory
function registered at import time.  ``seed_database()`` delegates to the
generic engine so the same loop can later seed non-warehouse domains.

Default warehouse profile:
- 200 SKUs across 8 categories with substitute chains
- 8 zones with varying initial congestion
- 50 shelves distributed across zones
- 10 workers positioned across zones
- 4 packing stations
- 2 dock doors
"""

from __future__ import annotations

import logging
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.simulation.config import (
    ArrivalRateConfig,
    EntityProfile,
    ResourceConstraints,
    SimulationConfig,
)
from core.simulation.engine import SimulationEngine, register_entity_factory
from domains.warehouse.models.inventory_item import SKU
from domains.warehouse.models.warehouse import (
    DockDoor,
    DockStatus,
    PackingStation,
    Shelf,
    StationStatus,
    Worker,
    WorkerStatus,
    Zone,
)

logger = logging.getLogger(__name__)

# ── Default warehouse configuration ───────────────────────────────────────

WAREHOUSE_SIMULATION_CONFIG = SimulationConfig(
    domain="warehouse",
    seed=42,
    entities=[
        EntityProfile(
            entity_type="zone",
            count=8,
            attributes={
                "names": [
                    "Zone-A Cold Storage",
                    "Zone-B Dry Goods",
                    "Zone-C Electronics",
                    "Zone-D Apparel",
                    "Zone-E Fragile",
                    "Zone-F Bulk",
                    "Zone-G Returns",
                    "Zone-H Express",
                ],
                "congestion_range": [0.05, 0.4],
            },
        ),
        EntityProfile(
            entity_type="sku",
            count=200,
            attributes={
                "categories": [
                    "Electronics",
                    "Groceries",
                    "Apparel",
                    "Home & Kitchen",
                    "Health & Beauty",
                    "Toys & Games",
                    "Office Supplies",
                    "Sports & Outdoors",
                ],
                "weight_range": [0.1, 15.0],
                "max_substitutes": 3,
            },
        ),
        EntityProfile(
            entity_type="shelf",
            count=50,
            attributes={
                "aisles": "ABCDEFGHIJ",
                "qty_range": [5, 100],
            },
        ),
        EntityProfile(
            entity_type="worker",
            count=10,
            attributes={
                "names": [
                    "Alice", "Bob", "Charlie", "Diana", "Eve",
                    "Frank", "Grace", "Hank", "Ivy", "Jack",
                ],
            },
        ),
        EntityProfile(
            entity_type="packing_station",
            count=4,
            attributes={"capacity": 5},
        ),
        EntityProfile(
            entity_type="dock_door",
            count=2,
            attributes={},
        ),
    ],
    arrival_rate=ArrivalRateConfig(
        lambda_per_minute=3.0,
        min_lambda=0.5,
        max_lambda=10.0,
        sla_window_minutes=(15, 60),
        items_per_event=(1, 5),
    ),
    resources=ResourceConstraints(
        max_concurrent_tasks=50,
        capacity_limits={"packing_stations": 4, "dock_doors": 2},
    ),
)


# ── Entity Factory Functions ──────────────────────────────────────────────

# Module-level caches used across factories during a single seed pass.
_zones: list[Zone] = []
_skus: list[SKU] = []


async def _create_zones(session: AsyncSession, profile: EntityProfile) -> int:
    """Create warehouse zones from profile config."""
    global _zones
    _zones = []
    names = profile.attributes.get("names", [f"Zone-{i}" for i in range(profile.count)])
    cmin, cmax = profile.attributes.get("congestion_range", [0.05, 0.4])

    for i in range(profile.count):
        name = names[i] if i < len(names) else f"Zone-{i}"
        z = Zone(name=name, congestion_level=round(random.uniform(cmin, cmax), 2))
        session.add(z)
        _zones.append(z)

    await session.flush()
    return len(_zones)


async def _create_skus(session: AsyncSession, profile: EntityProfile) -> int:
    """Create SKUs with substitute chains."""
    global _skus
    _skus = []
    categories = profile.attributes.get("categories", ["General"])
    wmin, wmax = profile.attributes.get("weight_range", [0.1, 15.0])
    max_subs = profile.attributes.get("max_substitutes", 3)

    for i in range(1, profile.count + 1):
        cat = categories[(i - 1) % len(categories)]
        sku = SKU(
            name=f"{cat}-Item-{i:03d}",
            category=cat,
            weight_kg=round(random.uniform(wmin, wmax), 2),
        )
        session.add(sku)
        _skus.append(sku)

    await session.flush()

    # Set substitute chains
    for sku in _skus:
        same_cat = [s for s in _skus if s.category == sku.category and s.id != sku.id]
        if same_cat:
            subs = random.sample(same_cat, min(max_subs, len(same_cat)))
            sku.substitute_sku_ids = [s.id for s in subs]
    await session.flush()

    return len(_skus)


async def _create_shelves(session: AsyncSession, profile: EntityProfile) -> int:
    """Create shelves distributed across zones."""
    aisles = profile.attributes.get("aisles", "ABCDEFGHIJ")
    qmin, qmax = profile.attributes.get("qty_range", [5, 100])
    count = 0

    for i in range(profile.count):
        zone = _zones[i % len(_zones)] if _zones else None
        sku = _skus[i % len(_skus)] if _skus else None
        shelf = Shelf(
            zone_id=zone.id if zone else None,
            aisle=aisles[i % len(aisles)],
            rack=(i // 10) + 1,
            level=(i % 4) + 1,
            sku_id=sku.id if sku else None,
            quantity=random.randint(qmin, qmax),
        )
        session.add(shelf)
        count += 1

    await session.flush()
    return count


async def _create_workers(session: AsyncSession, profile: EntityProfile) -> int:
    """Create workers positioned across zones."""
    names = profile.attributes.get(
        "names",
        [f"Worker-{i}" for i in range(profile.count)],
    )
    aisles = "ABCDEFGHIJ"
    count = 0

    for i in range(profile.count):
        name = names[i] if i < len(names) else f"Worker-{i}"
        zone = _zones[i % len(_zones)] if _zones else None
        worker = Worker(
            name=name,
            status=WorkerStatus.IDLE,
            current_zone_id=zone.id if zone else None,
            task_count=0,
            position_x=float(ord(aisles[i % len(aisles)])),
            position_y=float((i % 5) + 1),
        )
        session.add(worker)
        count += 1

    await session.flush()
    return count


async def _create_packing_stations(session: AsyncSession, profile: EntityProfile) -> int:
    """Create packing stations."""
    capacity = profile.attributes.get("capacity", 5)
    for i in range(1, profile.count + 1):
        ps = PackingStation(
            name=f"Pack-Station-{i}",
            capacity=capacity,
            current_load=0,
            status=StationStatus.AVAILABLE,
        )
        session.add(ps)
    await session.flush()
    return profile.count


async def _create_dock_doors(session: AsyncSession, profile: EntityProfile) -> int:
    """Create dock doors."""
    for i in range(1, profile.count + 1):
        dd = DockDoor(name=f"Dock-{i}", status=DockStatus.FREE)
        session.add(dd)
    await session.flush()
    return profile.count


# ── Register all warehouse factories ──────────────────────────────────────

register_entity_factory("zone", _create_zones)
register_entity_factory("sku", _create_skus)
register_entity_factory("shelf", _create_shelves)
register_entity_factory("worker", _create_workers)
register_entity_factory("packing_station", _create_packing_stations)
register_entity_factory("dock_door", _create_dock_doors)


# ── Public entry point ────────────────────────────────────────────────────

async def seed_database(
    session: AsyncSession,
    config: SimulationConfig | None = None,
) -> dict:
    """Seed the database with simulated warehouse data.

    Args:
        session: Async SQLAlchemy session.
        config:  Optional override config.  Defaults to
                 ``WAREHOUSE_SIMULATION_CONFIG``.

    Returns:
        Dictionary of entity counts, or ``{"status": "already_seeded"}``.
    """
    # Check if already seeded
    existing = await session.execute(select(SKU).limit(1))
    if existing.scalar_one_or_none():
        logger.info("Database already seeded — skipping")
        return {"status": "already_seeded"}

    cfg = config or WAREHOUSE_SIMULATION_CONFIG
    engine = SimulationEngine(cfg)
    counts = await engine.seed(session)
    await session.commit()

    logger.info("Database seeded: %s", counts)
    return counts
