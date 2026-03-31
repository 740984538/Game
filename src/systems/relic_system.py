"""
遗物系统 - 对应文档 §5.2 / §10.4.3
订阅事件总线，在各触发点应用持有遗物的效果
"""
from __future__ import annotations
from src.core.event_manager import event_manager

try:
    import esper
    class RelicProcessor(esper.Processor):
        def process(self, dt: float) -> None:
            # 遗物效果通过事件总线触发，此处无需每帧轮询
            # 遗物效果在 entities/relics/relic_manager.py 中通过订阅事件实现
            pass
except ImportError:
    class RelicProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
