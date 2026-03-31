"""遗物选择场景 - 对应文档 §5.2"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene


class RelicSelectScene(BaseScene):
    """展示多个遗物供玩家选择（通常3选1），对应 §5.2.2 稀有度分布"""

    def enter(self, relic_pool: list = None, count: int = 3, **kwargs) -> None:
        # TODO: 从遗物池中抽取指定数量遗物展示
        pass

    def update(self, dt: float) -> None:
        # TODO: 处理遗物选择
        pass

    def render(self, surface) -> None:
        # TODO: 渲染遗物卡片和说明
        pass
