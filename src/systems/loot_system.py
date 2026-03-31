"""
掉落系统 - 对应文档 §4.1.2 房间类型奖励
敌人死亡后生成金币/遗物掉落
"""
from __future__ import annotations
from src.core.event_manager import event_manager

try:
    import esper
    class LootProcessor(esper.Processor):
        def process(self, dt: float) -> None:
            # TODO: 监听 on_kill 事件，根据敌人配置生成掉落
            pass
except ImportError:
    class LootProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
