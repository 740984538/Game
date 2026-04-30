"""
游戏状态机
对应文档 §10.3.3 游戏状态机
"""
from __future__ import annotations
from typing import Dict, Optional, TYPE_CHECKING
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.scenes.base_scene import BaseScene


class StateMachine:
    """
    游戏状态机，管理所有场景（Scene）的切换。
    每个 GameState 对应一个 BaseScene 子类实例。
    """

    def __init__(self) -> None:
        self.states: Dict[GameState, "BaseScene"] = {}
        self.current_state: Optional["BaseScene"] = None
        self.current_game_state: Optional[GameState] = None

    def register(self, state: GameState, scene: "BaseScene") -> None:
        """注册一个状态对应的场景"""
        self.states[state] = scene

    def change(self, new_state: GameState, **kwargs) -> None:
        """
        切换到新状态。
        会依次调用：旧场景.exit() → 新场景.enter(**kwargs)
        """
        if self.current_state is not None:
            self.current_state.exit()

        if new_state not in self.states:
            raise KeyError(f"状态 {new_state} 尚未注册")

        self.current_state = self.states[new_state]
        self.current_game_state = new_state
        self.current_state.enter(**kwargs)

    def update(self, dt: float) -> None:
        """每帧更新当前场景"""
        if self.current_state:
            self.current_state.update(dt)

    def render(self, surface) -> None:
        """每帧渲染当前场景"""
        if self.current_state:
            self.current_state.render(surface)

    def handle_event(self, event) -> None:
        """将 pygame 事件传递给当前场景"""
        if self.current_state:
            self.current_state.handle_event(event)
