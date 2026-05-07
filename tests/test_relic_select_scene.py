"""
RelicSelectScene 单元测试 - 对应开发计划 8-5

验证：
  - enter() 接收 relic_pool 参数
  - 卡片数量与候选数量一致
  - 点击卡片选中
  - 确认按钮在选中后启用
  - 跳过按钮按 allow_skip 控制
  - 选定/跳过后 state_machine.change 被正确调用
"""
import pytest
from unittest.mock import MagicMock

try:
    import pygame  # noqa: F401
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.scenes.relic_select_scene import RelicSelectScene
from src.entities.relics.relic import RelicRegistry
from src.utils.enums import GameState


MOCK_POOL = {
    "iron_will":  {"id": "iron_will",  "name": "钢铁意志", "rarity": "common",
                   "description": "+20 HP", "effects": []},
    "blood_rage": {"id": "blood_rage", "name": "血怒", "rarity": "rare",
                   "description": "低血伤害+50%", "effects": []},
    "fire_heart": {"id": "fire_heart", "name": "火焰之心", "rarity": "legendary",
                   "description": "火伤+50%", "effects": []},
}


def _make_scene() -> RelicSelectScene:
    mock_game = MagicMock()
    mock_game.state_machine = MagicMock()
    scene = RelicSelectScene(mock_game)
    return scene


@pytest.fixture(autouse=True)
def _registry():
    RelicRegistry.reset()
    reg = RelicRegistry.instance()
    reg.load_from_pool(MOCK_POOL)
    yield reg
    RelicRegistry.reset()


class TestRelicSelectScene:

    def test_enter_builds_cards_for_each_id(self):
        scene = _make_scene()
        scene.enter(relic_pool=["iron_will", "blood_rage", "fire_heart"])
        assert len(scene._cards) == 3

    def test_enter_with_count_truncates(self):
        scene = _make_scene()
        scene.enter(
            relic_pool=["iron_will", "blood_rage", "fire_heart"],
            count=2,
        )
        assert len(scene._cards) == 2

    def test_enter_skips_unknown_relic(self):
        scene = _make_scene()
        scene.enter(relic_pool=["iron_will", "unknown_id", "fire_heart"])
        assert len(scene._cards) == 2
        ids = [c.relic.id for c in scene._cards]
        assert "unknown_id" not in ids

    def test_confirm_button_disabled_initially(self):
        scene = _make_scene()
        scene.enter(relic_pool=["iron_will", "blood_rage"])
        assert scene._confirm_btn is not None
        assert scene._confirm_btn.enabled is False

    def test_card_click_selects_and_enables_confirm(self):
        scene = _make_scene()
        scene.enter(relic_pool=["iron_will", "blood_rage"])

        first_card = scene._cards[0]
        scene._on_card_click(first_card)

        assert scene._selected_card is first_card
        assert first_card.selected is True
        assert scene._confirm_btn.enabled is True

    def test_clicking_second_card_swaps_selection(self):
        scene = _make_scene()
        scene.enter(relic_pool=["iron_will", "blood_rage"])

        c1, c2 = scene._cards[0], scene._cards[1]
        scene._on_card_click(c1)
        scene._on_card_click(c2)

        assert c1.selected is False
        assert c2.selected is True
        assert scene._selected_card is c2

    def test_confirm_returns_to_state(self):
        scene = _make_scene()
        scene.enter(
            relic_pool=["iron_will"],
            return_state=GameState.MAP_NAVIGATION,
            return_kwargs={"floor_number": 2},
        )
        scene._on_card_click(scene._cards[0])
        scene._on_confirm()

        scene.game.state_machine.change.assert_called_once()
        args, kwargs = scene.game.state_machine.change.call_args
        assert args[0] == GameState.MAP_NAVIGATION
        assert kwargs.get("picked_relic") == "iron_will"
        assert kwargs.get("floor_number") == 2

    def test_skip_returns_with_none(self):
        scene = _make_scene()
        scene.enter(
            relic_pool=["iron_will", "blood_rage"],
            return_state=GameState.MAP_NAVIGATION,
        )
        scene._on_skip()
        args, kwargs = scene.game.state_machine.change.call_args
        assert kwargs.get("picked_relic") is None

    def test_skip_disabled_when_allow_skip_false(self):
        scene = _make_scene()
        scene.enter(
            relic_pool=["iron_will"],
            allow_skip=False,
        )
        assert scene._skip_btn.enabled is False

    def test_on_pick_callback_invoked(self):
        callback_results = []
        scene = _make_scene()
        scene.enter(
            relic_pool=["iron_will"],
            on_pick=lambda rid: callback_results.append(rid),
        )
        scene._on_card_click(scene._cards[0])
        scene._on_confirm()
        assert callback_results == ["iron_will"]

    def test_empty_relic_pool_renders_message(self):
        scene = _make_scene()
        scene.enter(relic_pool=[])
        # 没有卡片
        assert len(scene._cards) == 0
        # 但 widgets 仍然有标题等
        assert len(scene._widgets) > 0
