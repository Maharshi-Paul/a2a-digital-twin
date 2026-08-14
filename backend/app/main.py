"""FastAPI application entrypoint with async lifespan management.

Lifespan stages:
1. Startup: Connect DB → Create tables → Connect Redis → Start agents → Start queue engine
2. Shutdown: Stop simulation → Stop queue engine → Stop agents → Disconnect bus → Dispose engine
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.a2a.bus import MessageBus
from app.agents.dock_agent import DockAgent
from app.agents.inventory_agent import InventoryAgent
from app.agents.order_coordinator import OrderCoordinatorAgent
from app.agents.packing_agent import PackingAgent
from app.agents.picking_agent import PickingAgent
from app.api.routes import router as api_router, set_refs
from app.api.websocket import router as ws_router, set_ws_refs
from app.config import settings
from app.database import async_session_factory, engine
from app.mcp.server import router as mcp_router, set_registry
from app.mcp.tools import MCPToolRegistry
from app.models import Base
from app.queue_engine.engine import QueueEngine
from app.simulation.generator import OrderGenerator

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Shared References ─────────────────────────────────────────────────────────
bus: MessageBus | None = None
queue_engine: QueueEngine | None = None
order_generator: OrderGenerator | None = None
order_coordinator: OrderCoordinatorAgent | None = None
agents: list = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — startup and shutdown."""
    global bus, queue_engine, order_generator, order_coordinator, agents

    logger.info("=" * 60)
    logger.info("WAREHOUSE DIGITAL TWIN — Starting Up")
    logger.info("=" * 60)

    # ── 1. Database ────────────────────────────────────────────────
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")

    # ── 2. Redis Message Bus ───────────────────────────────────────
    bus = MessageBus(settings.redis_url)
    await bus.connect()
    await bus.start_listening()

    # ── 3. MCP Tool Registry ──────────────────────────────────────
    mcp_registry = MCPToolRegistry(async_session_factory)
    set_registry(mcp_registry)
    logger.info("MCP tool registry initialized with %d tools", len(mcp_registry.list_tools()))

    # ── 4. Agents ──────────────────────────────────────────────────
    order_coordinator = OrderCoordinatorAgent(bus, async_session_factory)
    inventory_agent = InventoryAgent(bus, async_session_factory)
    picking_agent = PickingAgent(bus, async_session_factory)
    packing_agent = PackingAgent(bus, async_session_factory)
    dock_agent = DockAgent(bus, async_session_factory)

    agents = [
        order_coordinator,
        inventory_agent,
        picking_agent,
        packing_agent,
        dock_agent,
    ]

    for agent in agents:
        await agent.start()
    logger.info("All %d agents started", len(agents))

    # ── 5. Queue Engine ────────────────────────────────────────────
    queue_engine = QueueEngine(async_session_factory, bus)
    await queue_engine.start()

    # ── 6. Order Generator (not started — controlled via API) ──────
    order_generator = OrderGenerator(
        async_session_factory,
        on_order_created=order_coordinator.ingest_order,
    )

    # ── 7. Wire up API references ──────────────────────────────────
    set_refs(order_generator, order_coordinator, queue_engine)
    set_ws_refs(async_session_factory, queue_engine)

    logger.info("=" * 60)
    logger.info("WAREHOUSE DIGITAL TWIN — Ready")
    logger.info("  API: http://%s:%d/docs", settings.api_host, settings.api_port)
    logger.info("  WS:  ws://%s:%d/ws/live", settings.api_host, settings.api_port)
    logger.info("=" * 60)

    yield

    # ── Shutdown ───────────────────────────────────────────────────
    logger.info("Shutting down...")

    if order_generator and order_generator.is_running:
        await order_generator.stop()

    if queue_engine:
        await queue_engine.stop()

    for agent in agents:
        await agent.stop()

    if bus:
        await bus.disconnect()

    await engine.dispose()
    logger.info("Shutdown complete")


# ── App Factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Warehouse Digital Twin",
        description="Smart Agent-to-Agent, Queue-Aware Digital Twin for Warehouse Logistics",
        version="0.1.0",
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
    app.include_router(api_router)
    app.include_router(ws_router)
    app.include_router(mcp_router)

    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "agents": len(agents),
            "queue_cycles": queue_engine.cycle_count if queue_engine else 0,
            "orders_generated": order_generator.total_generated if order_generator else 0,
        }

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
