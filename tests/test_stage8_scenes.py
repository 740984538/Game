"""
阶段 8 场景单元测试 - 8-6/8-7/8-11/8-12/8-13/8-14

覆盖各场景的逻辑分支（不依赖 pygame 渲染）：
  - PauseScene: 进入参数保存、继续/放弃跳转
  - GameOverScene: 统计读取、灵魂碎片计算、按钮跳转
  - VictoryScene: 类似 GameOverScene 的胜利版本
  - RestScene: 休息恢复 30%HP / 锻造升级 / 跳过
  - ShopScene: 商品价格、购买扣金、售罄
  - EventScene: 事件加载、选项条件、outcome 应用
"""
import pytest
from unittest.mock import MagicMock

from src.utils.enums import GameState
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


def _make_game(with_run_state: bool = True) -> MagicMock:
    g = MagicMock()
    g.state_machine = MagicMock()
    if with_run_state:
        g.run_state = RunStateManager()
        g.run_state.start_new_run("knight", seed=1)
    else:
        g.run_state = None
    return g


# ═══════════════════════════════════════════════════════════════════════════════
# 8-14: PauseScene
# ═══════════════════════════════════════════════════════════════════════════════

class TestPauseScene:

    def setup_method(self):
        from src.scenes.pause_scene import PauseScene
        self.game = _make_game()
        self.scene = PauseScene(self.game)

    def test_enter_records_return_state(self):
        self.scene.enter(
            return_state=GameState.COMBAT,
            return_kwargs={"floor_number": 2, "character_id": "knight"},
        )
        assert self.scene._return_state == GameState.COMBAT
        assert self.scene._return_kwargs.get("floor_number") == 2

    def test_resume_changes_back(self):
        self.scene.enter(
            return_state=GameState.MAP_NAVIGATION,
            return_kwargs={"floor_number": 1},
        )
        self.scene._on_resume()
        args, kwargs = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.MAP_NAVIGATION
        assert kwargs.get("floor_number") == 1

    def test_abandon_goes_to_game_over(self):
        self.scene.enter(return_state=GameState.COMBAT)
        self.scene._do_abandon()
        args, kwargs = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.GAME_OVER
        assert kwargs.get("reason") == "abandon"
        # RunState 应该被结束
        assert self.scene.game.run_state.active is False


# ═══════════════════════════════════════════════════════════════════════════════
# 8-12: GameOverScene
# ═══════════════════════════════════════════════════════════════════════════════

class TestGameOverScene:

    def setup_method(self):
        from src.scenes.game_over_scene import GameOverScene
        self.game = _make_game()
        self.scene = GameOverScene(self.game)

    def test_enter_collects_stats_from_run_state(self):
        # 模拟一些战斗经历
        self.game.run_state.advance_floor()       # floors_cleared=1
        self.game.run_state.record_combat_result(victory=True, kills=3)
        self.game.run_state.add_gold(50)

        self.scene.enter(reason="death")
        assert self.scene._reason == "death"
        assert self.scene._stats_dict["floors_cleared"] == 1
        assert self.scene._stats_dict["total_kills"] == 3
        assert self.scene._stats_dict["gold_earned"] >= 50

    def test_soul_shards_calculation(self):
        self.game.run_state.advance_floor()       # +1 floor (5 shards)
        self.game.run_state.record_combat_result(victory=True, room_type="boss", kills=1)  # +20+1
        self.game.run_state.record_combat_result(victory=True, room_type="elite", kills=1) # +5+1
        self.scene.enter(reason="death")
        # = 5*1 + 20*1 + 5*1 + 1*(1+1) = 32
        assert self.scene._earned_shards == 5*1 + 20*1 + 5*1 + (1 + 1)

    def test_explicit_run_stats_override(self):
        explicit = {
            "character_id": "mage",
            "current_floor": 3,
            "total_kills": 99,
        }
        self.scene.enter(reason="abandon", run_stats=explicit)
        assert self.scene._stats_dict["character_id"] == "mage"
        assert self.scene._stats_dict["total_kills"] == 99

    def test_retry_goes_to_character_select(self):
        self.scene.enter(reason="death")
        self.scene._on_retry()
        args, _ = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.CHARACTER_SELECT
        assert self.game.run_state.active is False

    def test_main_menu_button(self):
        self.scene.enter(reason="death")
        self.scene._on_main_menu()
        args, _ = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.MAIN_MENU


# ═══════════════════════════════════════════════════════════════════════════════
# 8-13: VictoryScene
# ═══════════════════════════════════════════════════════════════════════════════

class TestVictoryScene:

    def setup_method(self):
        from src.scenes.victory_scene import VictoryScene
        self.game = _make_game()
        self.scene = VictoryScene(self.game)

    def test_enter_collects_stats(self):
        self.game.run_state.advance_floor()
        self.game.run_state.advance_floor()
        self.game.run_state.record_combat_result(victory=True, room_type="boss", kills=1)
        self.scene.enter()
        assert self.scene._stats_dict["floors_cleared"] == 2

    def test_soul_shards_includes_victory_bonus(self):
        from src.scenes.victory_scene import _VICTORY_BONUS_MULT
        self.game.run_state.record_combat_result(victory=True, room_type="boss", kills=1)
        self.scene.enter()
        # base = 1 (kill) + 20 (boss) + 5 (elite_kill=0... actually 0)
        # base = 21 → *1.5 = 31
        expected = int((1 + 20) * _VICTORY_BONUS_MULT)
        assert self.scene._earned_shards == expected

    def test_format_time(self):
        from src.scenes.victory_scene import VictoryScene
        assert VictoryScene._format_time(0) == "00:00"
        assert VictoryScene._format_time(65) == "01:05"
        assert VictoryScene._format_time(3600) == "60:00"

    def test_main_menu_button(self):
        self.scene.enter()
        self.scene._on_main_menu()
        args, _ = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.MAIN_MENU
        assert self.game.run_state.active is False


# ═══════════════════════════════════════════════════════════════════════════════
# 8-7: RestScene
# ═══════════════════════════════════════════════════════════════════════════════

class TestRestScene:

    def setup_method(self):
        from src.scenes.rest_scene import RestScene, REST_HEAL_PERCENT
        self.heal_percent = REST_HEAL_PERCENT
        self.game = _make_game()
        # 扣血以便测试治疗
        self.game.run_state.take_damage(40)
        self.scene = RestScene(self.game)

    def test_enter_keeps_return_kwargs(self):
        self.scene.enter(
            floor_number=2, character_id="knight",
            seed=1, daily=False, room_type="rest", node_id=5,
        )
        # 不应包含 room_type / node_id（它们由 MAP_NAVIGATION 自行管理）
        assert "room_type" not in self.scene._return_kwargs
        assert "node_id" not in self.scene._return_kwargs
        assert self.scene._return_kwargs.get("floor_number") == 2
        assert self.scene._return_kwargs.get("character_id") == "knight"

    def test_rest_heals_30_percent(self):
        max_hp = self.game.run_state.max_health
        old_hp = self.game.run_state.health
        self.scene.enter(floor_number=1, character_id="knight")
        self.scene._on_rest()
        expected_heal = int(max_hp * self.heal_percent)
        # 可能受 max_hp 上限影响
        actual = self.game.run_state.health - old_hp
        assert actual >= 1
        assert actual <= expected_heal + 1  # +1 容差

        # 应该跳转回地图
        args, _ = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.MAP_NAVIGATION

    def test_skip_returns_to_map(self):
        self.scene.enter(floor_number=1, character_id="knight")
        self.scene._on_skip()
        args, _ = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.MAP_NAVIGATION

    def test_forge_with_empty_deck_returns(self):
        self.game.run_state.deck = []
        self.scene.enter(floor_number=1, character_id="knight")
        self.scene._on_forge()
        # 空卡组应直接返回
        args, _ = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.MAP_NAVIGATION

    def test_upgrade_card_replaces_with_plus(self):
        self.game.run_state.deck = ["slash", "defend"]
        self.scene.enter(floor_number=1, character_id="knight")
        # 调用升级 handler
        handler = self.scene._make_upgrade_handler("slash")
        handler()
        assert "slash+" in self.game.run_state.deck
        assert "slash" not in self.game.run_state.deck


# ═══════════════════════════════════════════════════════════════════════════════
# 8-6: ShopScene
# ═══════════════════════════════════════════════════════════════════════════════

class TestShopScene:

    def setup_method(self):
        from src.scenes.shop_scene import ShopScene
        self.game = _make_game()
        self.game.run_state.gold = 1000
        self.scene = ShopScene(self.game)

    def test_enter_builds_items(self):
        self.scene.enter(
            floor_number=1, character_id="knight",
            seed=42, daily=False, node_id=3, room_type="shop",
        )
        # 至少一些遗物或卡牌商品
        assert len(self.scene._items) >= 1

    def test_buying_relic_grants_and_deducts(self):
        self.scene.enter(
            floor_number=1, character_id="knight",
            seed=42, node_id=3,
        )
        relic_items = [it for it in self.scene._items if it.item_kind == "relic"]
        if not relic_items:
            pytest.skip("没有遗物商品（小概率配置原因）")
        item = relic_items[0]
        old_gold = self.game.run_state.gold
        old_relic_count = len(self.game.run_state.get_relic_ids())

        self.scene._on_buy_item(item)

        assert self.game.run_state.gold == old_gold - item.price
        assert len(self.game.run_state.get_relic_ids()) == old_relic_count + 1
        assert item._sold is True

    def test_buying_card_grants_and_deducts(self):
        self.scene.enter(
            floor_number=1, character_id="knight",
            seed=42, node_id=3,
        )
        card_items = [it for it in self.scene._items if it.item_kind == "card"]
        if not card_items:
            pytest.skip("没有卡牌商品")
        item = card_items[0]
        old_gold = self.game.run_state.gold
        old_deck = list(self.game.run_state.deck)

        self.scene._on_buy_item(item)

        assert self.game.run_state.gold == old_gold - item.price
        assert len(self.game.run_state.deck) == len(old_deck) + 1
        assert item.item_id in self.game.run_state.deck

    def test_cannot_afford_blocks_purchase(self):
        self.scene.enter(
            floor_number=1, character_id="knight",
            seed=42, node_id=3,
        )
        if not self.scene._items:
            pytest.skip("无商品")
        item = self.scene._items[0]
        self.game.run_state.gold = 0
        self.scene._update_affordability()
        assert item._affordable is False
        # 购买操作不应生效
        self.scene._on_buy_item(item)
        assert item._sold is False

    def test_leave_shop_returns_to_map(self):
        self.scene.enter(
            floor_number=1, character_id="knight",
            seed=42, node_id=3,
        )
        self.scene._on_leave()
        args, _ = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.MAP_NAVIGATION


# ═══════════════════════════════════════════════════════════════════════════════
# 8-11: EventScene
# ═══════════════════════════════════════════════════════════════════════════════

class TestEventScene:

    def setup_method(self):
        from src.scenes.event_scene import EventScene
        self.game = _make_game()
        self.scene = EventScene(self.game)

    def test_enter_loads_event(self):
        self.scene.enter(
            event_id="mysterious_merchant",
            floor_number=1, character_id="knight",
            seed=7, node_id=2,
        )
        assert self.scene._event_data.get("id") == "mysterious_merchant"

    def test_random_event_when_no_id(self):
        self.scene.enter(
            floor_number=1, character_id="knight",
            seed=7, node_id=2,
        )
        # 必须从 events 池里取到一个
        assert "id" in self.scene._event_data

    def test_apply_outcome_gold_change(self):
        self.scene.enter(
            event_id="mysterious_merchant",
            floor_number=1, character_id="knight",
            seed=7, node_id=2,
        )
        old_gold = self.game.run_state.gold
        result = self.scene._apply_outcome({"gold": -50})
        assert "金币" in result
        assert self.game.run_state.gold == old_gold - 50

    def test_apply_outcome_hp_cost(self):
        self.scene.enter(
            event_id="mysterious_merchant",
            floor_number=1, character_id="knight",
            seed=7, node_id=2,
        )
        old_hp = self.game.run_state.health
        self.scene._apply_outcome({"hp_cost": 10})
        assert self.game.run_state.health == old_hp - 10

    def test_apply_outcome_hp_percent_cost(self):
        self.scene.enter(
            event_id="ancient_altar",
            floor_number=1, character_id="knight",
            seed=7, node_id=2,
        )
        max_hp = self.game.run_state.max_health
        result = self.scene._apply_outcome({"hp_percent_cost": 0.3})
        assert "失去" in result
        # 损失大约 30%
        assert self.game.run_state.health <= max_hp * 0.71

    def test_apply_outcome_random_relic(self):
        self.scene.enter(
            event_id="ancient_altar",
            floor_number=1, character_id="knight",
            seed=42, node_id=1,
        )
        old_relics = len(self.game.run_state.get_relic_ids())
        self.scene._apply_outcome({"reward": "random_relic"})
        assert len(self.game.run_state.get_relic_ids()) == old_relics + 1

    def test_apply_outcome_none_returns_neutral_text(self):
        self.scene.enter(
            event_id="mysterious_merchant",
            floor_number=1, character_id="knight",
            seed=1, node_id=1,
        )
        text = self.scene._apply_outcome(None)
        assert "离开" in text

    def test_check_condition_gold(self):
        self.scene.enter(
            event_id="mysterious_merchant",
            floor_number=1, character_id="knight",
            seed=1, node_id=1,
        )
        rs = self.game.run_state
        rs.gold = 60
        assert self.scene._check_condition("gold >= 50", rs) is True
        rs.gold = 30
        assert self.scene._check_condition("gold >= 50", rs) is False

    def test_event_death_goes_to_game_over(self):
        self.scene.enter(
            event_id="ancient_altar",
            floor_number=1, character_id="knight",
            seed=1, node_id=1,
        )
        # 把 HP 扣到 0
        rs = self.game.run_state
        rs.take_damage(rs.health)
        # 触发返回逻辑
        self.scene._return_to_map()
        args, _ = self.scene.game.state_machine.change.call_args
        assert args[0] == GameState.GAME_OVER
