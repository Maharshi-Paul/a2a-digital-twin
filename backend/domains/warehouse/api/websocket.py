"""WebSocket endpoint for live dashboard updates.

Broadcasts:
- Queue state (every scoring cycle)
- Agent messages (on A2A activity)
- Warehouse status (periodic snapshots)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import orjson
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import async_sessionmaker

from domains.warehouse.services.warehouse_service import WarehouseService

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections with a single singleton broadcast loop."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self._broadcast_task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
            if self._broadcast_task is None or self._broadcast_task.done():
                self._broadcast_task = asyncio.create_task(self._periodic_broadcast_loop())
        logger.info("WebSocket connected. Total: %d", len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
            if not self._connections and self._broadcast_task and not self._broadcast_task.done():
                self._broadcast_task.cancel()
                self._broadcast_task = None
        logger.info("WebSocket disconnected. Total: %d", len(self._connections))

    async def broadcast_json(self, data: dict) -> None:
        """Broadcast a JSON message to all connected clients."""
        if not self._connections:
            return

        payload = orjson.dumps(data)
        dead: list[WebSocket] = []

        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_bytes(payload)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                if ws in self._connections:
                    self._connections.remove(ws)

    @property
    def count(self) -> int:
        return len(self._connections)

    async def _periodic_broadcast_loop(self) -> None:
        """Broadcast warehouse state every 2 seconds only while clients are connected."""
        logger.info("Starting WebSocket singleton periodic broadcast loop")
        while True:
            try:
                if _session_factory and self.count > 0:
                    async with _session_factory() as session:
                        status = await WarehouseService.get_warehouse_status(session)
                        kpis = await WarehouseService.get_kpis(session)

                        queue_data = []
                        if _queue_engine:
                            scored = _queue_engine.get_last_scored()
                            queue_data = [
                                {
                                    "order_id": s.order_id,
                                    "external_id": s.external_id,
                                    "score": s.total_score,
                                    "sla_risk": s.sla_risk,
                                }
                                for s in scored[:20]
                            ]

                        logs = await WarehouseService.get_agent_logs(session, limit=10)

                        await self.broadcast_json({
                            "type": "state_update",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "warehouse": status,
                            "kpis": kpis,
                            "queue": queue_data,
                            "agent_logs": logs,
                            "connections": self.count,
                        })

                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                logger.info("WebSocket periodic broadcast loop cancelled (no active clients)")
                break
            except Exception:
                logger.exception("Broadcast error in periodic loop")
                await asyncio.sleep(2.0)


manager = ConnectionManager()

# Set at startup
_session_factory: async_sessionmaker | None = None
_queue_engine = None


def set_ws_refs(session_factory, queue_engine) -> None:
    global _session_factory, _queue_engine
    _session_factory = session_factory
    _queue_engine = queue_engine


@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """WebSocket endpoint for live dashboard data with heartbeat ping-pong."""
    await manager.connect(ws)

    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket connection error")
    finally:
        await manager.disconnect(ws)


async def broadcast_agent_event(event: dict) -> None:
    """Push a real-time agent event to all WebSocket clients."""
    await manager.broadcast_json({
        "type": "agent_event",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **event,
    })


async def broadcast_decision_commentary(
    order_id: int, external_id: str, commentary: str,
) -> None:
    """Push a Claude-generated decision commentary to all WebSocket clients."""
    await manager.broadcast_json({
        "type": "decision_commentary",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_id": order_id,
        "external_id": external_id,
        "commentary": commentary,
    })
