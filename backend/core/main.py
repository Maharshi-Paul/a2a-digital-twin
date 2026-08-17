"""Warehouse A2A Digital Twin — FastAPI Application Entrypoint.

Manages full lifecycle:
1. Database schema creation & seeding
2. Redis message bus connection
3. MCP tool registry initialization
4. Agent startup (all 5 warehouse agents)
5. Queue engine startup
6. Simulation generator startup

All are registered as lifespan-managed resources.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import async_session_factory, engine
from core.models.base import Base

# Import all models so SQLAlchemy registers them
from core.models.agent_log import AgentMessage  # noqa: F401
from domains.warehouse.models.order import Order, OrderItem  # noqa: F401
from domains.warehouse.models.inventory_item import SKU  # noqa: F401
from domains.warehouse.models.warehouse import (  # noqa: F401
    Zone, Shelf, Worker, PackingStation, DockDoor,
)

from core.a2a.message_bus import MessageBus

from domains.warehouse.agents.order_agent import OrderCoordinatorAgent
from domains.warehouse.agents.inventory_agent import InventoryAgent
from domains.warehouse.agents.picking_agent import PickingAgent
from domains.warehouse.agents.packing_agent import PackingAgent
from domains.warehouse.agents.dock_agent import DockAgent

from domains.warehouse.queue_engine.engine import WarehouseQueueEngine
from domains.warehouse.mcp.tools import WarehouseMCPToolRegistry
from domains.warehouse.mcp.server import set_mcp_registry
from domains.warehouse.simulation.order_generator import OrderGenerator
from domains.warehouse.simulation.seeder import seed_database

from core.api.health import router as health_router
from domains.warehouse.api.routes import router as warehouse_router, set_api_refs
from domains.warehouse.api.websocket import router as ws_router, set_ws_refs

# ── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("warehouse_twin")


# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Full lifecycle management — startup and shutdown."""
    logger.info("=" * 60)
    logger.info("  WAREHOUSE DIGITAL TWIN — Starting...")
    logger.info("=" * 60)

    # 1. Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    # 2. Seed database
    async with async_session_factory() as session:
        await seed_database(session)

    # 3. Connect message bus
    bus = MessageBus(settings.redis_url)
    await bus.connect()

    # 4. Initialize MCP registry
    mcp_registry = WarehouseMCPToolRegistry(async_session_factory)
    set_mcp_registry(mcp_registry)
    logger.info("MCP registry initialized with %d tools", mcp_registry.tool_count)

    # 5. Start agents
    order_coord = OrderCoordinatorAgent(bus, async_session_factory)
    inventory = InventoryAgent(bus, async_session_factory)
    picking = PickingAgent(bus, async_session_factory)
    packing = PackingAgent(bus, async_session_factory)
    dock = DockAgent(bus, async_session_factory)

    agents = [order_coord, inventory, picking, packing, dock]
    for agent in agents:
        await agent.start()
    logger.info("All %d agents started", len(agents))

    # 6. Start queue engine
    queue_engine = WarehouseQueueEngine(bus, async_session_factory)
    await queue_engine.start()

    # 7. Start simulation generator
    generator = OrderGenerator(
        async_session_factory,
        on_order_created=order_coord.ingest_order,
    )

    # 8. Wire up API and WebSocket refs
    set_api_refs(order_coord, queue_engine, generator)
    set_ws_refs(async_session_factory, queue_engine)

    # 9. Start message bus listener
    await bus.start_listening()

    logger.info("=" * 60)
    logger.info("  WAREHOUSE DIGITAL TWIN — Ready ✓")
    logger.info("  API: http://%s:%d", settings.api_host, settings.api_port)
    logger.info("  Docs: http://%s:%d/docs", settings.api_host, settings.api_port)
    logger.info("  WebSocket: ws://%s:%d/ws/live", settings.api_host, settings.api_port)
    logger.info("=" * 60)

    yield

    # ── Shutdown ───────────────────────────────────────────────────────
    logger.info("Shutting down...")
    await generator.stop()
    await queue_engine.stop()
    for agent in agents:
        await agent.stop()
    await bus.disconnect()
    await engine.dispose()
    logger.info("Warehouse Digital Twin stopped.")


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Warehouse A2A Digital Twin",
    description="Smart Agent-to-Agent, Queue-Aware Digital Twin for Warehouse Logistics",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health_router)
app.include_router(warehouse_router)
app.include_router(ws_router)

# Import MCP server router
from domains.warehouse.mcp.server import router as mcp_router  # noqa: E402
app.include_router(mcp_router)
