"""休息点场景 - 对应文档 §4.1.2"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene


class RestScene(BaseScene):
    """休息点：恢复生命值 或 升级一张卡牌（二选一）"""

    def enter(self, **kwargs) -> None:
        pass

    def update(self, dt: float) -> None:
        # TODO: 处理恢复/升级选择
        pass

    def render(self, surface) -> None:
        # TODO: 渲染休息点UI
        pass
