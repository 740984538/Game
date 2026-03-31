"""
状态机单元测试
验证场景切换逻辑
对应文档 §10.3.3 游戏状态机
"""
import pytest
from src.core.state_machine import StateMachine
from src.utils.enums import GameState


class MockScene:
    def __init__(self):
        self.entered = False
        self.exited = False
        self.enter_kwargs = {}

    def enter(self, **kwargs):
        self.entered = True
        self.enter_kwargs = kwargs

    def exit(self):
        self.exited = True

    def update(self, dt):
        pass

    def render(self, surface):
        pass


class TestStateMachine:
    def test_change_state(self):
        sm = StateMachine()
        scene_a = MockScene()
        scene_b = MockScene()
        sm.register(GameState.MAIN_MENU, scene_a)
        sm.register(GameState.CHARACTER_SELECT, scene_b)

        sm.change(GameState.MAIN_MENU)
        assert scene_a.entered
        assert sm.current_game_state == GameState.MAIN_MENU

        sm.change(GameState.CHARACTER_SELECT)
        assert scene_a.exited
        assert scene_b.entered
        assert sm.current_game_state == GameState.CHARACTER_SELECT

    def test_unregistered_state_raises(self):
        sm = StateMachine()
        with pytest.raises(KeyError):
            sm.change(GameState.COMBAT)

    def test_enter_kwargs_passed(self):
        sm = StateMachine()
        scene = MockScene()
        sm.register(GameState.COMBAT, scene)
        sm.change(GameState.COMBAT, room_type="elite", floor=3)
        assert scene.enter_kwargs == {"room_type": "elite", "floor": 3}
