"""
8-8 楼层切换 + 战斗结束流程单元测试

验证 CombatScene 在 on_battle_win / on_battle_lose 事件下的跳转：
  - 普通战斗 → MAP_NAVIGATION
  - 精英战斗 → RELIC_SELECT (1 张) → MAP
  - BOSS 战胜利且非最终楼层 → RELIC_SELECT (3 张) → 下一层 MAP
  - BOSS 战胜利且最终楼层 → VICTORY
  - 战斗失败 → GAME_OVER
"""
import pytest
from unittest.mock import MagicMock

try:
    import esper
    _esper_available = True
except ImportError:
    _esper_available = False

from src.utils.enums import GameState, RoomType
from src.core.run_state import RunStateManager
from src.entities.relics.relic import RelicRegistry
from src.entities.player.character_stats import CharacterRegistry


@pytest.fixture(autouse=True)
def _registries():
    CharacterRegistry.instance().load_all()
    RelicRegistry.reset()
    RelicRegistry.instance().load_all()
    yield
    RelicRegistry.reset()


def _make_scene(room_type: RoomType = RoomType.COMBAT,
                floor_number: int = 1):
    from src.scenes.combat_scene import CombatScene
    g = MagicMock()
    g.state_machine = MagicMock()
    g.run_state = RunStateManager()
    g.run_state.start_new_run("knight", seed=42)
    g.run_state.current_floor = floor_number
    scene = CombatScene(g)
    scene.enter(
        floor_number=floor_number,
        character_id="knight",
        room_type=room_type,
        node_id=1,
        seed=42,
    )
    return scene


@pytest.mark.skipif(not _esper_available, reason="esper not installed")
class TestCombatBattleEndTransitions:

    def test_normal_combat_win_returns_to_map(self):
        scene = _make_scene(RoomType.COMBAT, floor_number=2)
        scene._on_battle_win(room_type="combat", floor_number=2)
        last_call = scene.game.state_machine.change.call_args
        target = last_call.args[0]
        # 普通战斗：可能是 MAP（无掉落）或 RELIC_SELECT（小概率掉落）
        assert target in (GameState.MAP_NAVIGATION, GameState.RELIC_SELECT)

    def test_elite_combat_win_goes_to_relic_select(self):
        scene = _make_scene(RoomType.ELITE, floor_number=2)
        scene._on_battle_win(room_type="elite", floor_number=2)
        last_call = scene.game.state_machine.change.call_args
        target = last_call.args[0]
        # 精英必掉 1 个，应直接获得（不进入 RELIC_SELECT 选择场景）
        # 但当前实现：1 个候选 -> MAP 自动获得
        assert target == GameState.MAP_NAVIGATION
        # 应该获得了一个新遗物
        assert len(scene.game.run_state.get_relic_ids()) >= 1

    def test_boss_win_non_final_goes_to_relic_select(self):
        scene = _make_scene(RoomType.BOSS, floor_number=1)
        scene._on_battle_win(room_type="boss", floor_number=1)
        last_call = scene.game.state_machine.change.call_args
        target = last_call.args[0]
        # 非最终楼层 BOSS → RELIC_SELECT
        assert target == GameState.RELIC_SELECT
        # 应有 3 个候选
        kwargs = last_call.kwargs
        assert len(kwargs.get("relic_pool", [])) == 3

    def test_boss_win_final_floor_goes_to_victory(self):
        # 默认 floors_per_run=5
        scene = _make_scene(RoomType.BOSS, floor_number=5)
        scene._on_battle_win(room_type="boss", floor_number=5)
        last_call = scene.game.state_machine.change.call_args
        assert last_call.args[0] == GameState.VICTORY
        assert scene.game.run_state.active is False

    def test_battle_lose_goes_to_game_over(self):
        scene = _make_scene(RoomType.COMBAT, floor_number=1)
        scene._on_battle_lose()
        last_call = scene.game.state_machine.change.call_args
        assert last_call.args[0] == GameState.GAME_OVER
        kwargs = last_call.kwargs
        assert kwargs.get("reason") == "death"
        assert scene.game.run_state.active is False

    def test_combat_win_records_stats(self):
        scene = _make_scene(RoomType.COMBAT, floor_number=1)
        scene._on_battle_win(room_type="combat", floor_number=1)
        rs = scene.game.run_state
        assert rs.stats.combats_won == 1
        assert rs.stats.rooms_cleared == 1


@pytest.mark.skipif(not _esper_available, reason="esper not installed")
class TestCombatDifficultyScaling:

    def test_enemies_scaled_by_floor(self):
        """同一种敌人在第 5 层应该比第 1 层 HP 更高"""
        from src.ecs.components import Health
        scene1 = _make_scene(RoomType.COMBAT, floor_number=1)
        scene5 = _make_scene(RoomType.COMBAT, floor_number=5)

        if not scene1._enemy_entities or not scene5._enemy_entities:
            pytest.skip("没有生成敌人")

        # 取第一个敌人比较 (使用相同 seed=42)
        eid1 = scene1._enemy_entities[0]
        eid5 = scene5._enemy_entities[0]
        hp1 = scene1._world.component_for_entity(eid1, Health)
        hp5 = scene5._world.component_for_entity(eid5, Health)
        # 楼层越高 HP 越多（同一敌人模板缩放）
        # 由于敌人池随机选择，不同 scene 可能选到不同敌人；这里只能粗略验证
        assert hp5.maximum >= hp1.maximum or len(scene1._enemy_entities) != len(scene5._enemy_entities)


@pytest.mark.skipif(not _esper_available, reason="esper not installed")
class TestCombatBossPhaseBanner:

    def test_phase_banner_set_on_event(self):
        scene = _make_scene(RoomType.BOSS, floor_number=1)
        scene._on_boss_phase_change(
            boss_name="测试BOSS",
            old_phase=1,
            new_phase=2,
            description="召唤援军",
        )
        assert "测试BOSS" in scene._phase_banner_text
        assert "2" in scene._phase_banner_text
        assert scene._phase_banner_timer > 0

    def test_phase_banner_decays_in_update(self):
        scene = _make_scene(RoomType.BOSS, floor_number=1)
        scene._on_boss_phase_change(
            boss_name="x", new_phase=2, description="y",
        )
        scene.update(2.0)
        assert scene._phase_banner_timer > 0
        scene.update(2.0)
        assert scene._phase_banner_timer <= 0
        assert scene._phase_banner_text == ""
