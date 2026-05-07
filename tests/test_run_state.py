"""
RunStateManager 单元测试 - 阶段 8 跨场景玩家状态

验证：
  - start_new_run 初始化角色 HP/金币/卡组/起始遗物
  - take_damage / heal / add_max_health
  - add_gold / can_afford / add_essence
  - add_card / remove_card
  - add_relic（含 on_pickup 副作用）
  - advance_floor / record_combat_result / 统计累加
  - to_dict 序列化
"""
import pytest
from src.core.run_state import RunStateManager, RunStatistics
from src.entities.relics.relic import RelicRegistry
from src.entities.player.character_stats import CharacterRegistry


@pytest.fixture(autouse=True)
def _registries():
    # 真实加载角色 + 遗物
    CharacterRegistry.instance().load_all()
    RelicRegistry.reset()
    RelicRegistry.instance().load_all()
    yield
    RelicRegistry.reset()


class TestRunStateLifecycle:

    def test_start_new_run_loads_knight_defaults(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=42)
        assert rs.active is True
        assert rs.character_id == "knight"
        assert rs.seed == 42
        assert rs.current_floor == 1
        assert rs.health > 0
        assert rs.health == rs.max_health
        # knight 起始金币
        assert rs.gold > 0
        # 遗物管理器已初始化
        assert rs.relic_manager is not None

    def test_starting_relic_applied(self):
        """如果角色配置了 starting_relic，应该立即被加入"""
        rs = RunStateManager()
        rs.start_new_run("knight", seed=42)
        # knight 默认起始遗物（如有）
        from src.entities.player.character_stats import CharacterRegistry
        char = CharacterRegistry.instance().get("knight")
        if char and char.starting_relic:
            assert rs.has_relic(char.starting_relic)

    def test_unknown_character_falls_back(self):
        rs = RunStateManager()
        rs.start_new_run("non_existent", seed=1)
        # 使用默认值
        assert rs.health > 0
        assert rs.max_health > 0

    def test_end_run(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=1)
        rs.end_run()
        assert rs.active is False


class TestRunStateMutations:

    def setup_method(self):
        self.rs = RunStateManager()
        self.rs.start_new_run("knight", seed=1)

    def test_take_damage(self):
        old_hp = self.rs.health
        actual = self.rs.take_damage(10)
        assert actual == 10
        assert self.rs.health == old_hp - 10
        assert self.rs.stats.total_damage_taken == 10

    def test_take_damage_floors_at_zero(self):
        actual = self.rs.take_damage(99999)
        assert actual <= 99999
        assert self.rs.health == 0
        assert not self.rs.is_alive()

    def test_heal_caps_at_max(self):
        self.rs.take_damage(20)
        healed = self.rs.heal(99999)
        assert self.rs.health == self.rs.max_health
        assert healed == 20

    def test_add_max_health(self):
        old_max = self.rs.max_health
        old_hp = self.rs.health
        self.rs.add_max_health(20)
        assert self.rs.max_health == old_max + 20
        assert self.rs.health == old_hp + 20

    def test_add_max_health_negative(self):
        old_max = self.rs.max_health
        self.rs.add_max_health(-10)
        assert self.rs.max_health == old_max - 10

    def test_add_gold(self):
        old = self.rs.gold
        self.rs.add_gold(50)
        assert self.rs.gold == old + 50
        assert self.rs.stats.gold_earned == 50

    def test_add_gold_negative_clamped_at_zero(self):
        self.rs.add_gold(-99999)
        assert self.rs.gold == 0

    def test_add_gold_capped(self):
        self.rs.add_gold(99999)
        from src.utils.constants import GOLD_CAP
        assert self.rs.gold == GOLD_CAP

    def test_can_afford(self):
        self.rs.gold = 100
        assert self.rs.can_afford(50)
        assert self.rs.can_afford(100)
        assert not self.rs.can_afford(101)

    def test_add_essence_capped(self):
        from src.utils.constants import ESSENCE_CAP
        self.rs.add_essence(99999)
        assert self.rs.essence == ESSENCE_CAP

    def test_add_card_remove_card(self):
        self.rs.add_card("slash")
        assert "slash" in self.rs.deck
        assert self.rs.remove_card("slash")
        assert "slash" not in self.rs.deck
        assert not self.rs.remove_card("slash")  # 已不在


class TestRunStateRelics:

    def test_add_relic_applies_max_health_bonus(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=1)
        old_max = rs.max_health
        ok = rs.add_relic("iron_will")  # +20 HP
        assert ok
        assert rs.has_relic("iron_will")
        # 应该应用了 max_health_bonus
        assert rs.max_health == old_max + 20

    def test_add_unknown_relic_returns_false(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=1)
        assert not rs.add_relic("non_existent_relic")

    def test_get_relic_ids(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=1)
        starting = list(rs.get_relic_ids())
        rs.add_relic("iron_will")
        ids = rs.get_relic_ids()
        assert "iron_will" in ids
        assert len(ids) == len(starting) + 1


class TestRunStateProgress:

    def test_advance_floor(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=1)
        assert rs.current_floor == 1
        new = rs.advance_floor()
        assert new == 2
        assert rs.current_floor == 2
        assert rs.stats.floors_cleared == 1

    def test_record_combat_result_victory(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=1)
        rs.record_combat_result(victory=True, room_type="combat",
                                kills=2, damage_dealt=50, cards_played=3)
        assert rs.stats.combats_won == 1
        assert rs.stats.rooms_cleared == 1
        assert rs.stats.total_kills == 2
        assert rs.stats.cards_played == 3
        assert rs.stats.total_damage_dealt == 50
        assert rs.last_battle["victory"] is True

    def test_record_combat_result_elite_kill(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=1)
        rs.record_combat_result(victory=True, room_type="elite", kills=1)
        assert rs.stats.elite_kills == 1
        assert rs.stats.bosses_killed == 0

    def test_record_combat_result_boss_kill(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=1)
        rs.record_combat_result(victory=True, room_type="boss", kills=1)
        assert rs.stats.bosses_killed == 1

    def test_record_combat_result_loss_records_killed_by(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=1)
        rs.record_combat_result(victory=False, killed_by="骸骨之王")
        assert rs.stats.last_killed_by == "骸骨之王"

    def test_to_dict(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=42, daily=True, difficulty=2)
        d = rs.to_dict()
        assert d["character_id"] == "knight"
        assert d["seed"] == 42
        assert d["daily"] is True
        assert d["difficulty"] == 2
        assert "deck" in d
        assert "relics" in d
        assert "stats" in d
