"""
战斗场景单元测试
对应开发计划: 5-3 (布局), 5-4 (玩家显示), 5-5 (敌人显示)
测试逻辑层面的正确性 (不依赖 pygame 渲染)
"""
import pytest
from unittest.mock import MagicMock, patch

try:
    import esper
    _esper_available = True
except ImportError:
    _esper_available = False

from src.scenes.combat_scene import (
    CombatScene,
    _HEADER_H, _HAND_AREA_H, _BATTLE_AREA_H,
    _PLAYER_AREA_X, _PLAYER_AREA_Y,
    _ENEMY_AREA_X, _ENEMY_AREA_Y,
    _HP_BAR_W,
)
from src.ecs.components import (
    Position, Sprite, Health, Stats, Block, Energy,
    PlayerTag, EnemyTag, IntentDisplay, BossController,
)
from src.utils.enums import GameState, RoomType
from src.utils.constants import SCREEN_WIDTH, SCREEN_HEIGHT


def _make_scene() -> CombatScene:
    """创建带 mock game 的场景实例"""
    mock_game = MagicMock()
    mock_game.state_machine = MagicMock()
    return CombatScene(mock_game)


class TestCombatLayout:
    """5-3: 战斗场景布局测试"""

    def test_layout_constants_valid(self):
        """布局常量组合覆盖整个屏幕高度"""
        total = _HEADER_H + _BATTLE_AREA_H + _HAND_AREA_H
        assert total == SCREEN_HEIGHT

    def test_player_area_in_left_half(self):
        """玩家区域在屏幕左半部分"""
        assert _PLAYER_AREA_X < SCREEN_WIDTH // 2

    def test_enemy_area_in_right_half(self):
        """敌人区域在屏幕右半部分"""
        assert _ENEMY_AREA_X > SCREEN_WIDTH // 2

    def test_hand_area_at_bottom(self):
        """手牌区在屏幕底部"""
        hand_y = SCREEN_HEIGHT - _HAND_AREA_H
        assert hand_y > SCREEN_HEIGHT * 0.7


@pytest.mark.skipif(not _esper_available, reason="esper not installed")
class TestCombatSceneInit:
    """5-3/5-4/5-5: 场景初始化测试"""

    def test_enter_creates_world(self):
        """enter() 初始化 ECS 世界"""
        scene = _make_scene()
        scene.enter(
            character_id="knight",
            room_type=RoomType.COMBAT,
            floor_number=1,
        )
        assert scene._world is not None
        assert scene._player_entity >= 0

    def test_player_has_required_components(self):
        """玩家实体包含所有必要组件"""
        scene = _make_scene()
        scene.enter(character_id="knight", room_type=RoomType.COMBAT)
        world = scene._world

        eid = scene._player_entity
        assert world.has_component(eid, Position)
        assert world.has_component(eid, Sprite)
        assert world.has_component(eid, Health)
        assert world.has_component(eid, Stats)
        assert world.has_component(eid, Block)
        assert world.has_component(eid, Energy)
        assert world.has_component(eid, PlayerTag)

    def test_player_position_in_player_area(self):
        """玩家实体位于玩家区域内"""
        scene = _make_scene()
        scene.enter(character_id="knight", room_type=RoomType.COMBAT)
        world = scene._world

        pos = world.component_for_entity(scene._player_entity, Position)
        # 在玩家区域范围内
        assert pos.x >= _PLAYER_AREA_X
        assert pos.x <= _PLAYER_AREA_X + 400
        assert pos.y >= _HEADER_H

    def test_enemies_spawned_for_combat(self):
        """普通战斗生成 1-3 个敌人"""
        scene = _make_scene()
        scene.enter(character_id="knight", room_type=RoomType.COMBAT)
        assert 1 <= len(scene._enemy_entities) <= 3

    def test_elite_spawns_one_enemy(self):
        """精英战斗生成 1 个敌人"""
        scene = _make_scene()
        scene.enter(character_id="knight", room_type=RoomType.ELITE)
        assert len(scene._enemy_entities) == 1

    def test_enemies_have_required_components(self):
        """敌人实体包含所有必要组件"""
        scene = _make_scene()
        scene.enter(character_id="knight", room_type=RoomType.COMBAT)
        world = scene._world

        for eid in scene._enemy_entities:
            assert world.has_component(eid, Position)
            assert world.has_component(eid, Sprite)
            assert world.has_component(eid, Health)
            assert world.has_component(eid, EnemyTag)
            assert world.has_component(eid, IntentDisplay)

    def test_enemies_in_enemy_area(self):
        """敌人位于敌人区域内"""
        scene = _make_scene()
        scene.enter(character_id="knight", room_type=RoomType.COMBAT)
        world = scene._world

        for eid in scene._enemy_entities:
            pos = world.component_for_entity(eid, Position)
            assert pos.x >= _ENEMY_AREA_X - 50
            assert pos.x <= _ENEMY_AREA_X + 500

    def test_boss_spawn(self):
        """BOSS 战生成 BOSS 实体"""
        scene = _make_scene()
        scene.enter(character_id="knight", room_type=RoomType.BOSS)
        assert len(scene._enemy_entities) >= 1

        world = scene._world
        boss_eid = scene._enemy_entities[0]
        tag = world.component_for_entity(boss_eid, EnemyTag)
        assert tag.enemy_type == "boss"

    def test_exit_clears_world(self):
        """exit() 清理实体"""
        scene = _make_scene()
        scene.enter(character_id="knight", room_type=RoomType.COMBAT)
        assert scene._player_entity >= 0

        scene.exit()
        assert scene._player_entity == -1
        assert len(scene._enemy_entities) == 0


class TestCombatRenderHelpers:
    """渲染辅助函数逻辑测试 (不需要 pygame)"""

    def test_intent_colors_defined(self):
        """所有意图类型都有对应颜色"""
        from src.scenes.combat_scene import _INTENT_COLORS
        for intent_type in ["attack", "defend", "buff", "debuff", "unknown"]:
            assert intent_type in _INTENT_COLORS
            color = _INTENT_COLORS[intent_type]
            assert len(color) == 3

    def test_layout_no_overlap(self):
        """玩家区和敌人区不重叠"""
        from src.scenes.combat_scene import _PLAYER_AREA_W, _ENEMY_AREA_W
        player_right = _PLAYER_AREA_X + _PLAYER_AREA_W
        assert player_right < _ENEMY_AREA_X
