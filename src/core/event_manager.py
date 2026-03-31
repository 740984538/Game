"""
内部事件总线（发布/订阅模式）
解耦各系统之间的通信，对应文档 §10.3 核心架构
"""
from __future__ import annotations
from collections import defaultdict
from typing import Callable, Dict, List, Any


class EventManager:
    """
    轻量级事件总线。
    系统通过 subscribe/publish 进行解耦通信，
    避免系统间直接引用。

    典型事件名称示例：
      - "on_hit"           : 攻击命中时
      - "on_kill"          : 击杀敌人时
      - "on_damaged"       : 玩家受到伤害时
      - "on_death"         : 实体死亡时
      - "on_floor_start"   : 进入新楼层时
      - "on_floor_end"     : 完成当前楼层时
      - "on_relic_picked"  : 拾取遗物时
      - "on_shop_open"     : 开启商店时
      - "on_crit"          : 暴击触发时
      - "on_block"         : 格挡成功时
    """

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable) -> None:
        """订阅事件"""
        self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable) -> None:
        """取消订阅"""
        listeners = self._listeners.get(event, [])
        if callback in listeners:
            listeners.remove(callback)

    def publish(self, event: str, **kwargs: Any) -> None:
        """发布事件，同步调用所有订阅者"""
        for callback in list(self._listeners.get(event, [])):
            callback(**kwargs)

    def clear(self) -> None:
        """清空所有订阅（换局时调用）"""
        self._listeners.clear()


# 全局单例
event_manager = EventManager()
