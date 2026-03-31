"""
遗物数据类与管理器 - 对应文档 §10.4.3
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from src.core.event_manager import event_manager


@dataclass
class RelicEffect:
    """单条遗物效果"""
    trigger: str          # 触发事件名，如 'on_hit', 'on_kill'
    effect_type: str      # 效果类型
    value: float          # 效果数值
    condition: Optional[str] = None  # 触发条件表达式（可选）


class Relic:
    """遗物实体，对应文档 §5.2"""

    def __init__(self, relic_id: str, config: dict) -> None:
        self.id = relic_id
        self.name: str = config["name"]
        self.rarity: str = config["rarity"]
        self.description: str = config.get("description", "")
        self.effects: List[RelicEffect] = [
            RelicEffect(**e) for e in config.get("effects", [])
        ]

    def apply(self, event: str, context: dict) -> dict:
        """根据触发事件应用效果，返回修改后的上下文"""
        for effect in self.effects:
            if effect.trigger == event:
                context = self._apply_effect(effect, context)
        return context

    def _apply_effect(self, effect: RelicEffect, context: dict) -> dict:
        """将单条效果应用到上下文（简单加减乘除）"""
        # TODO: 根据 effect_type 执行具体逻辑
        return context


class RelicManager:
    """
    管理玩家当局持有的遗物列表，并通过事件总线触发效果。
    对应文档 §10.4.3 遗物系统
    """

    def __init__(self, relic_pool: Dict[str, dict]) -> None:
        self.active_relics: List[Relic] = []
        self._pool = relic_pool

    def add_relic(self, relic_id: str) -> None:
        """拾取遗物，将其加入当局 Build"""
        if relic_id not in self._pool:
            return
        relic = Relic(relic_id, self._pool[relic_id])
        self.active_relics.append(relic)
        event_manager.publish("on_relic_picked", relic=relic)

    def trigger(self, event: str, context: dict) -> dict:
        """触发所有持有遗物中与该事件匹配的效果"""
        for relic in self.active_relics:
            context = relic.apply(event, context)
        return context

    def clear(self) -> None:
        self.active_relics.clear()
