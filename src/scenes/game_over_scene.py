"""游戏结束场景 - 对应文档 §2.2.1 死亡流程"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene


class GameOverScene(BaseScene):
    """
    死亡结算界面：
    - 展示本局统计（层数、击杀数、获得的遗物）
    - 结算灵魂碎片
    - 提供"再来一局"和"返回主菜单"选项
    """

    def enter(self, run_stats: dict = None, **kwargs) -> None:
        # TODO: 读取本局统计数据，计算灵魂碎片奖励
        pass

    def update(self, dt: float) -> None:
        pass

    def render(self, surface) -> None:
        # TODO: 渲染结算界面
        pass
