"""角色选择场景 - 对应文档 §5.1"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene


class CharacterSelectScene(BaseScene):
    """展示可用角色列表，选择后切换到 MAP_NAVIGATION"""

    def enter(self, **kwargs) -> None:
        # TODO: 加载所有角色配置
        pass

    def update(self, dt: float) -> None:
        # TODO: 处理角色选择输入
        pass

    def render(self, surface) -> None:
        # TODO: 渲染角色卡片
        pass
