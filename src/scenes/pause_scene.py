"""暂停菜单场景 - 对应文档 §6.1.1 Layer 5"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene


class PauseScene(BaseScene):
    """暂停菜单：继续游戏、查看遗物/卡牌、设置、放弃本局"""

    def enter(self, **kwargs) -> None:
        pass

    def update(self, dt: float) -> None:
        # TODO: 处理暂停菜单按键
        pass

    def render(self, surface) -> None:
        # TODO: 在当前画面上叠加半透明遮罩和菜单
        pass
