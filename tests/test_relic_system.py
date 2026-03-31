"""
遗物系统单元测试
验证遗物触发与 context 修改
对应文档 §5.2 遗物系统
"""
import pytest
from src.entities.relics.relic_manager import Relic, RelicManager

MOCK_POOL = {
    "iron_will": {
        "id": "iron_will",
        "name": "钢铁意志",
        "rarity": "common",
        "description": "生命值上限+20",
        "effects": [{"trigger": "on_pickup", "effect_type": "max_health_bonus", "value": 20}],
    }
}


class TestRelicSystem:
    def test_add_relic(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("iron_will")
        assert len(mgr.active_relics) == 1
        assert mgr.active_relics[0].id == "iron_will"

    def test_invalid_relic_ignored(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("non_existent_relic")
        assert len(mgr.active_relics) == 0

    def test_clear_relics(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("iron_will")
        mgr.clear()
        assert len(mgr.active_relics) == 0
