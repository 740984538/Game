"""
Buff/Debuff 系统 - 对应文档 §5.3 / §3.1.1 特殊机制
每帧处理 Buff 持续时间衰减和 tick 效果（如燃烧持续伤害）
"""
from __future__ import annotations
from src.ecs.components import BuffList, Health
from src.core.event_manager import event_manager

try:
    import esper
    class BuffProcessor(esper.Processor):
        def process(self, dt: float) -> None:
            for ent, (buff_list, health) in self.world.get_components(BuffList, Health):
                expired = []
                for buff in buff_list.buffs:
                    buff["duration"] -= dt
                    # 燃烧伤害 tick
                    if buff.get("type") == "burning":
                        dmg = int(buff.get("dps", 5) * dt)
                        health.current = max(0, health.current - dmg)
                    if buff["duration"] <= 0:
                        expired.append(buff)
                for b in expired:
                    buff_list.buffs.remove(b)
except ImportError:
    class BuffProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
