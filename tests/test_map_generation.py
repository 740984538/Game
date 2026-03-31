"""
地图生成单元测试
验证生成的楼层地图结构合法性
对应文档 §4.1.3 地图生成规则
"""
import pytest
import random
from src.generation.map_generator import MapGenerator
from src.utils.enums import RoomType


MOCK_FLOOR_CONFIG = {
    "room_weights": {"combat": 50, "elite": 10, "shop": 15, "event": 15, "rest": 10}
}


class TestMapGeneration:
    def _make_generator(self, seed: int = 12345) -> MapGenerator:
        rng = random.Random(seed)
        return MapGenerator(rng)

    def test_same_seed_same_map(self):
        """相同种子生成相同地图（§8.3.1）"""
        gen1 = self._make_generator(99999)
        gen2 = self._make_generator(99999)
        floor1 = gen1.generate_floor(1, MOCK_FLOOR_CONFIG)
        floor2 = gen2.generate_floor(1, MOCK_FLOOR_CONFIG)
        ids1 = [(n.room_type, n.row, n.col) for n in floor1.nodes]
        ids2 = [(n.room_type, n.row, n.col) for n in floor2.nodes]
        assert ids1 == ids2

    def test_floor_has_boss(self):
        """每层必须有一个BOSS节点"""
        gen = self._make_generator()
        floor = gen.generate_floor(1, MOCK_FLOOR_CONFIG)
        boss_nodes = [n for n in floor.nodes if n.room_type == RoomType.BOSS]
        assert len(boss_nodes) == 1

    def test_entry_connected(self):
        """入口节点有至少一条前向连接"""
        gen = self._make_generator()
        floor = gen.generate_floor(1, MOCK_FLOOR_CONFIG)
        entry = next(n for n in floor.nodes if n.node_id == floor.entry_node_id)
        assert len(entry.connections) >= 1
