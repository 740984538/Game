"""
UI 系统 - 对应文档 §6 UI/UX 设计规范
每帧刷新 HUD（血条、能量、遗物栏）
"""
from __future__ import annotations

try:
    import esper
    class UIProcessor(esper.Processor):
        def process(self, dt: float) -> None:
            # TODO: 更新 HUD 数据（从 ECS 组件读取并推送到 UI 控件）
            pass
except ImportError:
    class UIProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
