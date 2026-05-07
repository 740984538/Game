"""
RelicRegistry 单元测试 - 对应开发计划 8-2 (遗物配置读取)

验证：
  - 单例特性
  - load_all 从 config/relics 真实加载
  - load_from_pool 直接构造
  - get / all_relics / filter_by_rarity / __contains__
"""
import pytest
from src.entities.relics.relic import RelicRegistry, Relic
from src.utils.enums import Rarity


MOCK_POOL = {
    "iron_will":   {"id": "iron_will",   "name": "钢铁意志", "rarity": "common",
                    "description": "+20 HP",
                    "effects": [{"trigger": "on_pickup", "effect_type": "max_health_bonus", "value": 20}]},
    "blood_rage":  {"id": "blood_rage",  "name": "血怒", "rarity": "rare",
                    "description": "低血伤害+50%",
                    "effects": []},
    "fire_heart":  {"id": "fire_heart",  "name": "火焰之心", "rarity": "legendary",
                    "description": "火伤+50%",
                    "effects": []},
}


class TestRelicRegistry:

    def setup_method(self):
        RelicRegistry.reset()

    def teardown_method(self):
        RelicRegistry.reset()

    def test_singleton(self):
        a = RelicRegistry.instance()
        b = RelicRegistry.instance()
        assert a is b

    def test_load_from_pool(self):
        reg = RelicRegistry.instance()
        reg.load_from_pool(MOCK_POOL)
        assert reg.is_loaded
        assert len(reg) == 3
        assert "iron_will" in reg

    def test_get_returns_relic(self):
        reg = RelicRegistry.instance()
        reg.load_from_pool(MOCK_POOL)
        relic = reg.get("iron_will")
        assert isinstance(relic, Relic)
        assert relic.name == "钢铁意志"

    def test_get_missing_returns_none(self):
        reg = RelicRegistry.instance()
        reg.load_from_pool(MOCK_POOL)
        assert reg.get("does_not_exist") is None

    def test_filter_by_rarity_string(self):
        reg = RelicRegistry.instance()
        reg.load_from_pool(MOCK_POOL)
        commons = reg.filter_by_rarity("common")
        assert len(commons) == 1
        assert commons[0].id == "iron_will"

    def test_filter_by_rarity_enum(self):
        reg = RelicRegistry.instance()
        reg.load_from_pool(MOCK_POOL)
        legendaries = reg.filter_by_rarity(Rarity.LEGENDARY)
        assert len(legendaries) == 1
        assert legendaries[0].id == "fire_heart"

    def test_all_relics_sorted(self):
        reg = RelicRegistry.instance()
        reg.load_from_pool(MOCK_POOL)
        ids = [r.id for r in reg.all_relics()]
        assert ids == sorted(ids)

    def test_raw_pool_returns_copy(self):
        reg = RelicRegistry.instance()
        reg.load_from_pool(MOCK_POOL)
        raw = reg.raw_pool()
        raw["new_key"] = {}
        # 修改 raw 不应影响 registry
        assert "new_key" not in reg.raw_pool()

    def test_load_all_from_real_config(self):
        """从真实 config/relics 加载，至少应包含已知遗物"""
        reg = RelicRegistry.instance()
        reg.load_all()
        assert reg.is_loaded
        assert len(reg) >= 5
        # 真实配置中存在的遗物
        assert "iron_will" in reg
        assert reg.get("iron_will").rarity == "common"
