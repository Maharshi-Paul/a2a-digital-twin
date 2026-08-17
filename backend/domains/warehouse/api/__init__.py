from domains.warehouse.api.routes import router as warehouse_router, set_api_refs
from domains.warehouse.api.websocket import router as ws_router, set_ws_refs

__all__ = ["warehouse_router", "ws_router", "set_api_refs", "set_ws_refs"]
