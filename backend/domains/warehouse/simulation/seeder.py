"""Database seeder — populates the warehouse simulation environment.

Creates:
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

CATEGORIES = [
    "Electronics",
    "Groceries",
    "Apparel",
    "Home & Kitchen",
    "Health & Beauty",
    "Toys & Games",
    "Office Supplies",
    "Sports & Outdoors",
]

ZONE_NAMES = [
    "Zone-A Cold Storage",
    "Zone-B Dry Goods",
    "Zone-C Electronics",
    "Zone-D Apparel",
    "Zone-E Fragile",
    "Zone-F Bulk",
    "Zone-G Returns",
    "Zone-H Express",
]


async def seed_database(session: AsyncSession) -> dict:
    """Seed the database with simulated warehouse data. Returns counts."""
    # Check if already seeded
    existing = await session.execute(select(SKU).limit(1))
    if existing.scalar_one_or_none():
        logger.info("Database already seeded — skipping")
        return {"status": "already_seeded"}

    random.seed(42)  # Reproducible

    # ── Zones ──────────────────────────────────────────────────────
    zones = []
    for name in ZONE_NAMES:
        z = Zone(name=name, congestion_level=round(random.uniform(0.05, 0.4), 2))
        session.add(z)
        zones.append(z)
    await session.flush()
    logger.info("Created %d zones", len(zones))

    # ── SKUs ───────────────────────────────────────────────────────
    skus = []
    for i in range(1, 201):
        cat = CATEGORIES[(i - 1) % len(CATEGORIES)]
        sku = SKU(
            name=f"{cat}-Item-{i:03d}",
            category=cat,
            weight_kg=round(random.uniform(0.1, 15.0), 2),
        )
        session.add(sku)
        skus.append(sku)
    await session.flush()

    # Set substitute chains (each SKU points to 1-3 others in same category)
    for sku in skus:
        same_cat = [s for s in skus if s.category == sku.category and s.id != sku.id]
        if same_cat:
            subs = random.sample(same_cat, min(3, len(same_cat)))
            sku.substitute_sku_ids = [s.id for s in subs]
    await session.flush()
    logger.info("Created %d SKUs with substitute chains", len(skus))

    # ── Shelves ────────────────────────────────────────────────────
    shelves = []
    aisles = "ABCDEFGHIJ"
    for i in range(50):
        zone = zones[i % len(zones)]
        sku = skus[i % len(skus)]
        shelf = Shelf(
            zone_id=zone.id,
            aisle=aisles[i % len(aisles)],
            rack=(i // 10) + 1,
            level=(i % 4) + 1,
            sku_id=sku.id,
            quantity=random.randint(5, 100),
        )
        session.add(shelf)
        shelves.append(shelf)
    await session.flush()
    logger.info("Created %d shelves", len(shelves))

    # ── Workers ────────────────────────────────────────────────────
    worker_names = [
        "Alice", "Bob", "Charlie", "Diana", "Eve",
        "Frank", "Grace", "Hank", "Ivy", "Jack",
    ]
    workers = []
    for i, name in enumerate(worker_names):
        zone = zones[i % len(zones)]
        worker = Worker(
            name=name,
            status=WorkerStatus.IDLE,
            current_zone_id=zone.id,
            task_count=0,
            position_x=float(ord(aisles[i % len(aisles)])),
            position_y=float((i % 5) + 1),
        )
        session.add(worker)
        workers.append(worker)
    await session.flush()
    logger.info("Created %d workers", len(workers))

    # ── Packing Stations ──────────────────────────────────────────
    for i in range(1, 5):
        ps = PackingStation(
            name=f"Pack-Station-{i}",
            capacity=5,
            current_load=0,
            status=StationStatus.AVAILABLE,
        )
        session.add(ps)
    await session.flush()
    logger.info("Created 4 packing stations")

    # ── Dock Doors ────────────────────────────────────────────────
    for i in range(1, 3):
        dd = DockDoor(
            name=f"Dock-{i}",
            status=DockStatus.FREE,
        )
        session.add(dd)
    await session.flush()
    logger.info("Created 2 dock doors")

    await session.commit()

    counts = {
        "skus": len(skus),
        "zones": len(zones),
        "shelves": len(shelves),
        "workers": len(workers),
        "packing_stations": 4,
        "dock_doors": 2,
    }
    logger.info("Database seeded: %s", counts)
    return counts
