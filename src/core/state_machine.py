"""
游戏状态机
对应文档 §10.3.3 游戏状态机
"""
from __future__ import annotations
from typing import Callable, Dict, List, Optional, TYPE_CHECKING
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.scenes.base_scene import BaseScene


class StateMachine:
    """
    游戏状态机，管理所有场景（Scene）的切换。
    每个 GameState 对应一个 BaseScene 子类实例。

    支持注册 *change_listener*（阶段 9-7 用于 BGM 自动切换）。
    """

    def __init__(self) -> None:
        self.states: Dict[GameState, "BaseScene"] = {}
        self.current_state: Optional["BaseScene"] = None
        self.current_game_state: Optional[GameState] = None
        self._listeners: List[Callable[[GameState], None]] = []

    def register(self, state: GameState, scene: "BaseScene") -> None:
        self.states[state] = scene

    def add_change_listener(self, callback: Callable[[GameState], None]) -> None:
        """注册状态切换回调，change() 完成后会被调用，传入新的 GameState。"""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_change_listener(self, callback: Callable[[GameState], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def change(self, new_state: GameState, **kwargs) -> None:
        """切换到新状态。依次：旧场景.exit() -> 新场景.enter(**kwargs)"""
        if self.current_state is not None:
            self.current_state.exit()
        if new_state not in self.states:
            raise KeyError(f"状态 {new_state} 尚未注册")
        self.current_state = self.states[new_state]
        self.current_game_state = new_state
        self.current_state.enter(**kwargs)
        for cb in list(self._listeners):
            try:
                cb(new_state)
            except Exception:  # noqa: BLE001
                pass

    def update(self, dt: float) -> None:
        if self.current_state:
            self.current_state.update(dt)

    def render(self, surface) -> None:
        if self.current_state:
            self.current_state.render(surface)

    def handle_event(self, event) -> None:
        if self.current_state:
            self.current_state.handle_event(event)
