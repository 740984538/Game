"""
场景基类
所有游戏场景继承此类，对应文档 §6.1.1 界面层级
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.game import Game


class BaseScene(ABC):
    """
    场景基类，定义场景生命周期接口：
    enter → update(循环) → render(循环) → exit
    """

    def __init__(self, game: "Game") -> None:
        self.game = game

    def enter(self, **kwargs) -> None:
        """进入场景时调用，用于初始化场景状态"""
        pass

    def exit(self) -> None:
        """离开场景时调用，用于清理资源"""
        pass

    def handle_event(self, event) -> None:
        """处理 pygame 事件，子类可覆盖"""
        pass

    @abstractmethod
    def update(self, dt: float) -> None:
        """每帧更新逻辑，dt 单位为秒"""
        ...

    @abstractmethod
    def render(self, surface) -> None:
        """每帧渲染到 surface"""
        ...
