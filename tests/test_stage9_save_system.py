"""
阶段 9-1 / 9-2 / 9-3：存档系统集成测试

覆盖：
- MetaProgress 9-1 新字段（seen_cards / perm_upgrades / total_runs）
- SaveManager 单例 + 元进度迁移
- 当局存档保存→加载→删除→has_run_state 状态查询
- RunStateManager <-> RunState 模型互转（继续游戏功能）
"""
import os
import pytest

from src.data.save_manager import SaveManager
from src.data.models import MetaProgress, RunState, PlayerRunState, SAVE_VERSION
from src.core.run_state import RunStateManager

TEST_DB = "saves/test_stage9_save.db"


@pytest.fixture(autouse=True)
def cleanup():
    SaveManager.reset_instance()
    yield
    SaveManager.reset_instance()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


class TestMetaProgressFields:
    def test_default_new_fields_present(self):
        m = MetaProgress()
        assert m.seen_cards == []
        assert m.perm_upgrades == {}
        assert m.total_runs == 0
        assert m.total_victories == 0

    def test_see_helpers_idempotent(self):
        m = MetaProgress()
        assert m.see_relic("iron_will")
        assert not m.see_relic("iron_will")
        assert "iron_will" in m.seen_relics
        assert m.see_card("strike")
        assert not m.see_card("strike")
        assert m.see_enemy("slime")
        assert not m.see_enemy("slime")

    def test_unlock_character_idempotent(self):
        m = MetaProgress()
        assert m.unlock_character("mage")
        assert not m.unlock_character("mage")
        assert "mage" in m.unlocked_characters

    def test_save_version_constant(self):
        assert SAVE_VERSION


class TestSaveManagerSingleton:
    def test_instance_returns_same_object(self):
        m1 = SaveManager.instance(TEST_DB)
        m2 = SaveManager.instance(TEST_DB)
        assert m1 is m2

    def test_reset_creates_new(self):
        m1 = SaveManager.instance(TEST_DB)
        SaveManager.reset_instance()
        m2 = SaveManager.instance(TEST_DB)
        assert m1 is not m2


class TestMetaProgressPersistence:
    def test_save_and_load_round_trip(self):
        sm = SaveManager.instance(TEST_DB)
        meta = MetaProgress(soul_shards=500)
        meta.seen_cards = ["strike", "defend"]
        meta.perm_upgrades = {"hp_bonus": 3}
        meta.total_runs = 5
        meta.total_victories = 2
        sm.save_meta_progress(meta)

        # 强制重新加载（清掉单例缓存）
        SaveManager.reset_instance()
        sm2 = SaveManager.instance(TEST_DB)
        loaded = sm2.load_meta_progress()
        assert loaded.soul_shards == 500
        assert loaded.seen_cards == ["strike", "defend"]
        assert loaded.perm_upgrades == {"hp_bonus": 3}
        assert loaded.total_runs == 5
        assert loaded.total_victories == 2

    def test_add_soul_shards(self):
        sm = SaveManager.instance(TEST_DB)
        sm.add_soul_shards(100)
        sm.add_soul_shards(50)
        assert sm.load_meta_progress().soul_shards == 150

    def test_spend_soul_shards(self):
        sm = SaveManager.instance(TEST_DB)
        sm.add_soul_shards(100)
        assert sm.spend_soul_shards(40)
        assert sm.load_meta_progress().soul_shards == 60
        # 不足
        assert not sm.spend_soul_shards(999)
        assert sm.load_meta_progress().soul_shards == 60

    def test_record_run_finished(self):
        sm = SaveManager.instance(TEST_DB)
        sm.record_run_finished(victory=True)
        sm.record_run_finished(victory=False)
        sm.record_run_finished(victory=True)
        meta = sm.load_meta_progress()
        assert meta.total_runs == 3
        assert meta.total_victories == 2


class TestRunStatePersistence:
    def test_run_state_save_load_delete(self):
        sm = SaveManager.instance(TEST_DB)
        assert not sm.has_run_state()

        run = RunState(
            seed=42, floor=3, difficulty=1, daily=True,
            player=PlayerRunState(
                character_id="mage", health=55, max_health=70,
                gold=300, essence=2,
                relics=["iron_will", "blood_rage"],
                cards=["strike", "strike", "defend"],
            ),
            run_stats={"total_kills": 12, "play_seconds": 240.0},
        )
        sm.save_run_state(run)
        assert sm.has_run_state()

        loaded = sm.load_run_state()
        assert loaded.seed == 42
        assert loaded.floor == 3
        assert loaded.daily is True
        assert loaded.player.character_id == "mage"
        assert loaded.player.health == 55
        assert "iron_will" in loaded.player.relics
        assert loaded.run_stats["total_kills"] == 12

        sm.delete_run_state()
        assert not sm.has_run_state()
        assert sm.load_run_state() is None


class TestRunStateManagerSerialization:
    def test_round_trip_via_to_run_state_model(self):
        rs = RunStateManager()
        rs.start_new_run("knight", seed=999, daily=False)
        rs.add_gold(50)
        rs.add_essence(2)

        model = rs.to_run_state_model()
        assert model.seed == 999
        assert model.player.character_id == "knight"
        assert model.player.gold == rs.gold
        assert model.player.health == rs.health

        # 恢复到新的管理器
        rs2 = RunStateManager()
        rs2.restore_from_run_state_model(model)
        assert rs2.character_id == "knight"
        assert rs2.gold == rs.gold
        assert rs2.health == rs.health
        assert rs2.max_health == rs.max_health
        assert rs2.deck == rs.deck
