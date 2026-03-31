"""
存档管理单元测试
验证元进度和当局进度的序列化/反序列化
对应文档 §7.1 存档系统
"""
import os
import pytest
from src.data.save_manager import SaveManager
from src.data.models import MetaProgress, RunState, PlayerRunState

TEST_DB = "saves/test_game.db"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


class TestSaveManager:
    def test_save_and_load_meta_progress(self):
        mgr = SaveManager(TEST_DB)
        meta = MetaProgress(soul_shards=500, unlocked_characters=["knight", "mage"])
        mgr.save_meta_progress(meta)
        loaded = mgr.load_meta_progress()
        assert loaded.soul_shards == 500
        assert "mage" in loaded.unlocked_characters
        mgr.close()

    def test_default_meta_progress(self):
        """数据库为空时返回默认元进度"""
        mgr = SaveManager(TEST_DB)
        meta = mgr.load_meta_progress()
        assert meta.soul_shards == 0
        assert "knight" in meta.unlocked_characters
        mgr.close()

    def test_save_and_load_run_state(self):
        mgr = SaveManager(TEST_DB)
        run = RunState(seed=12345, floor=3)
        mgr.save_run_state(run)
        loaded = mgr.load_run_state()
        assert loaded.seed == 12345
        assert loaded.floor == 3
        mgr.close()

    def test_delete_run_state(self):
        mgr = SaveManager(TEST_DB)
        run = RunState(seed=99)
        mgr.save_run_state(run)
        mgr.delete_run_state()
        loaded = mgr.load_run_state()
        assert loaded is None
        mgr.close()
