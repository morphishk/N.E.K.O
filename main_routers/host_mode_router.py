"""[DESIGN-REF: P3-N2-T-HOST-01] Host Mode REST API"""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Optional

from modules.host_mode.manager import host_mode_manager
from app.integration_state import integration_state

router = APIRouter(tags=["host-mode"])


class HostModeRequest(BaseModel):
    action: str  # register / unregister / heartbeat / update
    host_app: Optional[str] = None
    features: Optional[List[str]] = None
    origin: Optional[str] = None
    config: Optional[dict] = None


def _host_mode_ctx():
    """[DESIGN-REF: P3-N2-T-HOST-09] 注入 Host Mode 状态到模板上下文"""
    import json
    return {"host_mode": json.dumps(integration_state.to_dict())}


@router.get("/api/host-mode")
async def get_host_mode():
    """查询当前 Host Mode 状态"""
    return host_mode_manager._response()


@router.post("/api/host-mode")
async def post_host_mode(req: HostModeRequest):
    """Host Mode 动作分发——integration_state 同步由 manager 内部统一处理"""
    action = req.action
    if action == "register":
        return await host_mode_manager.register(
            host_app=req.host_app or "unknown",
            features=req.features or [],
            origin=req.origin,
            config=req.config,
        )
    elif action == "unregister":
        return await host_mode_manager.unregister()
    elif action == "heartbeat":
        return await host_mode_manager.heartbeat()
    elif action == "update":
        return await host_mode_manager.update(
            features=req.features,
            config=req.config,
        )
    return {"error": f"Unknown action: {action}"}
