"""主菜单场景 - 对应文档 §6.1"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene
from src.utils.enums import GameState


class MainMenuScene(BaseScene):
    """主菜单：开始游戏、每日挑战、图鉴、设置、退出"""

    def enter(self, **kwargs) -> None:
        # TODO: 加载主菜单背景音乐和UI元素
        pass

    def update(self, dt: float) -> None:
        # TODO: 处理按钮点击，切换到 CHARACTER_SELECT
        pass

    def render(self, surface) -> None:
        # TODO: 渲染主菜单界面
        pass
