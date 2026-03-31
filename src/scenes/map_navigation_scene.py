"""地图导航场景 - 对应文档 §4.1"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene


class MapNavigationScene(BaseScene):
    """
    显示当前层的节点地图，玩家选择路径进入下一房间。
    对应文档 §4.1.3 地图生成规则
    """

    def enter(self, **kwargs) -> None:
        # TODO: 从 kwargs 获取楼层信息，渲染节点图
        pass

    def update(self, dt: float) -> None:
        # TODO: 处理节点点击，切换到对应房间场景
        pass

    def render(self, surface) -> None:
        # TODO: 渲染地图节点和路径
        pass
