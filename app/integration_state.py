"""[DESIGN-REF: P3-N2-T-HOST-01] N.E.K.O 集成全局状态单例

约束：
- 纯内存状态，不持久化（持久化由 manager.py 负责）
- 多进程安全：仅在 main_server 进程中读写，其他进程通过 HTTP API 查询
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HostModeState:
    registered: bool = False
    host_app: Optional[str] = None
    features: List[str] = field(default_factory=list)
    registered_at: Optional[float] = None
    origin: Optional[str] = None  # 注册时记录的 vcp-mate origin，用于 postMessage 校验
    config: dict = field(default_factory=dict)  # 额外配置，如 assist_types

    def to_dict(self) -> dict:
        return {
            "registered": self.registered,
            "host_app": self.host_app,
            "features": self.features,
            "registered_at": self.registered_at,
            "config": self.config,
        }


# 全局单例
integration_state = HostModeState()
