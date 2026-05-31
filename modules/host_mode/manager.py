"""[DESIGN-REF: P3-N2-T-HOST-01~T-HOST-08] Host Mode 状态管理单例

4 个 action：register / unregister / heartbeat / update
心跳超时 300s 自动 unregister
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from app.integration_state import integration_state

HOST_MODE_FILE = Path("data/host_mode.json")


class HostModeManager:
    def __init__(self):
        self.registered: bool = False
        self.host_app: Optional[str] = None
        self.features: list[str] = []
        self.registered_at: Optional[float] = None
        self.origin: Optional[str] = None
        self.config: dict = {}
        self._timer: Optional[asyncio.TimerHandle] = None
        self._load()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    async def register(self, host_app: str, features: list[str], origin: Optional[str] = None, config: Optional[dict] = None):
        """注册 Host Mode

        [DESIGN-REF: SUP-HOST-01~05] vcp-mate 注册时提供 config，N.E.K.O 合并并存储。
        config 中可包含 aux_proxy_base_url / aux_proxy_api_key，用于 Host Mode 自动代理。
        """
        self.registered = True
        self.host_app = host_app
        self.features = features
        self.registered_at = time.time()
        self.origin = origin

        # 基础配置：assist_types（realtime/tts 排除）
        base_config = {
            "assist_types": ["conversation", "vision", "summary", "emotion", "agent", "correction"],
        }

        # 客户端提供的 config（如 aux_proxy_base_url / aux_proxy_api_key）
        client_config = config or {}

        # 若客户端未提供代理地址，从 origin 推断默认地址
        proxy_base_url = client_config.get("aux_proxy_base_url")
        if not proxy_base_url and origin:
            # origin 如 http://localhost:6628 → 拼接为代理模板
            proxy_base_url = f"{origin}/v1/neko/{{character}}"
        if not proxy_base_url:
            proxy_base_url = "http://localhost:6628/v1/neko/{character}"

        proxy_api_key = client_config.get("aux_proxy_api_key", "dummy")

        base_config["aux_proxy_base_url"] = proxy_base_url
        base_config["aux_proxy_api_key"] = proxy_api_key

        # 合并客户端提供的其他 config 字段（保留客户端的自定义扩展）
        merged = {**base_config, **{k: v for k, v in client_config.items() if k not in base_config}}
        self.config = merged

        self._sync_integration_state()
        self._persist()
        self._schedule_unregister()
        logger.info(f"[HostMode] registered by {host_app}, features={features}, origin={origin}, config_keys={list(self.config.keys())}")
        return self._response()

    async def unregister(self):
        """注销 Host Mode"""
        self.registered = False
        self.host_app = None
        self.features = []
        self.registered_at = None
        self.origin = None
        self.config = {}
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._sync_integration_state()
        self._persist()
        logger.info("[HostMode] unregistered")
        return self._response()

    async def heartbeat(self):
        """心跳续期"""
        if not self.registered:
            return self._response()
        self.registered_at = time.time()
        self._sync_integration_state()
        self._schedule_unregister()
        return self._response()

    async def update(self, features: Optional[list[str]] = None, config: Optional[dict] = None):
        """更新注册信息（不修改 host_app）"""
        if features is not None:
            self.features = features
        if config is not None:
            self.config = {**self.config, **config}
        self._sync_integration_state()
        self._persist()
        return self._response()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _sync_integration_state(self):
        """同步内存状态到全局单例"""
        integration_state.registered = self.registered
        integration_state.host_app = self.host_app
        integration_state.features = self.features
        integration_state.registered_at = self.registered_at
        integration_state.origin = self.origin
        integration_state.config = self.config

    def _response(self) -> dict:
        return {
            "registered": self.registered,
            "host_app": self.host_app,
            "features": self.features,
            "registered_at": self.registered_at,
            "config": self.config,
        }

    def _persist(self):
        try:
            HOST_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
            HOST_MODE_FILE.write_text(
                json.dumps({
                    "registered": self.registered,
                    "host_app": self.host_app,
                    "features": self.features,
                    "registered_at": self.registered_at,
                    "origin": self.origin,
                    "config": self.config,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"[HostMode] 持久化失败: {e}")

    def _load(self):
        if not HOST_MODE_FILE.exists():
            return
        try:
            data = json.loads(HOST_MODE_FILE.read_text(encoding="utf-8"))
            self.registered = data.get("registered", False)
            self.host_app = data.get("host_app")
            self.features = data.get("features", [])
            self.registered_at = data.get("registered_at")
            self.origin = data.get("origin")
            self.config = data.get("config", {})
            self._sync_integration_state()
        except Exception as e:
            logger.warning(f"[HostMode] 加载失败: {e}")

    def _schedule_unregister(self):
        if self._timer:
            self._timer.cancel()
        loop = asyncio.get_event_loop()
        self._timer = loop.call_later(300, self._on_timeout)

    def _on_timeout(self):
        if self.registered:
            asyncio.create_task(self.unregister())
            logger.info("[HostMode] 心跳超时 300s，自动注销")


host_mode_manager = HostModeManager()
