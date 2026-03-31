"""随机事件场景 - 对应文档 §7.3"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene


class EventScene(BaseScene):
    """随机事件：展示事件描述和多个选项，根据选择给予奖励/惩罚"""

    def enter(self, event_id: str = None, **kwargs) -> None:
        # TODO: 加载事件配置，展示选项
        pass

    def update(self, dt: float) -> None:
        # TODO: 处理选项点击
        pass

    def render(self, surface) -> None:
        # TODO: 渲染事件界面
        pass
