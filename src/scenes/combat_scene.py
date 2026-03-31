"""战斗场景 - 对应文档 §4.2"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene


class CombatScene(BaseScene):
    """
    核心战斗场景，驱动 ECS 世界进行战斗循环。
    战斗结束后根据结果切换到 RELIC_SELECT / GAME_OVER / MAP_NAVIGATION
    """

    def enter(self, room_config: dict = None, **kwargs) -> None:
        # TODO: 初始化 ECS 世界，生成玩家和敌人实体
        pass

    def update(self, dt: float) -> None:
        # TODO: 驱动 ECS world.process(dt)
        pass

    def render(self, surface) -> None:
        # TODO: 渲染战斗场景（由 render_system 处理）
        pass

    def exit(self) -> None:
        # TODO: 销毁临时实体，保存战斗结果
        pass
