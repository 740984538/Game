"""
地图生成单元测试
验证生成的楼层地图结构合法性
对应文档 §4.1.3 地图生成规则

覆盖:
- 任务 4-1: MapNode 数据结构 (序列化、状态管理)
- 任务 4-2: 地图生成算法 (节点数量、连通性、类型分配、渲染坐标)
"""
import pytest
import random
from src.generation.map_generator import MapGenerator, MapNode, Floor
from src.utils.enums import RoomType


MOCK_FLOOR_CONFIG = {
    "room_weights": {"combat": 50, "elite": 10, "shop": 15, "event": 15, "rest": 10}
}

STANDARD_CONFIG = {
    "nodes_min": 8,
    "nodes_max": 12,
    "room_weights": {"combat": 50, "elite": 10, "shop": 15, "event": 15, "rest": 10}
}

SMALL_CONFIG = {
    "nodes_min": 4,
    "nodes_max": 5,
    "room_weights": {"combat": 0, "elite": 0, "shop": 100, "event": 0, "rest": 0}
}


class TestMapGeneration:
    """原有测试 (向后兼容)"""

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


class TestMapNodeDataStructure:
    """任务 4-1: 地图节点数据结构测试"""

    def test_mapnode_has_render_coords(self):
        """MapNode 包含渲染坐标 x, y"""
        node = MapNode(node_id=0, room_type=RoomType.COMBAT, row=0, col=0)
        assert hasattr(node, "x")
        assert hasattr(node, "y")
        assert node.x == 0.0
        assert node.y == 0.0

    def test_mapnode_has_state_fields(self):
        """MapNode 包含状态字段: visited, available, is_cleared, is_current"""
        node = MapNode(node_id=0, room_type=RoomType.COMBAT, row=0, col=0)
        assert node.visited is False
        assert node.available is False
        assert node.is_cleared is False
        assert node.is_current is False

    def test_mapnode_serialization(self):
        """MapNode 可以序列化和反序列化"""
        node = MapNode(
            node_id=5, room_type=RoomType.ELITE, row=2, col=1,
            x=300.0, y=450.0, connections=[6, 7],
            visited=True, available=False, is_cleared=True, is_current=True,
        )
        d = node.to_dict()
        restored = MapNode.from_dict(d)
        assert restored.node_id == 5
        assert restored.room_type == RoomType.ELITE
        assert restored.row == 2
        assert restored.col == 1
        assert restored.x == 300.0
        assert restored.y == 450.0
        assert restored.connections == [6, 7]
        assert restored.visited is True
        assert restored.is_cleared is True
        assert restored.is_current is True

    def test_floor_get_node_by_id(self):
        """Floor.get_node_by_id 能正确查找节点"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)
        # 能找到入口节点
        entry = floor.get_node_by_id(floor.entry_node_id)
        assert entry is not None
        assert entry.node_id == floor.entry_node_id
        # 找不到不存在的节点返回 None
        assert floor.get_node_by_id(9999) is None

    def test_floor_get_nodes_by_type(self):
        """Floor.get_nodes_by_type 能按类型过滤"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)
        boss_nodes = floor.get_nodes_by_type(RoomType.BOSS)
        assert len(boss_nodes) == 1
        assert boss_nodes[0].node_id == floor.boss_node_id

    def test_floor_get_available_nodes(self):
        """Floor.get_available_nodes 初始返回第一行节点"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)
        available = floor.get_available_nodes()
        # 入口标记为 current, 第一行节点标记为 available
        assert len(available) >= 2
        # 所有可用节点都在 row 0 (第一行) 或 entry
        for n in available:
            assert n.row in (-1, 0)

    def test_floor_get_current_node(self):
        """Floor.get_current_node 初始返回入口节点"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)
        current = floor.get_current_node()
        assert current is not None
        assert current.node_id == floor.entry_node_id

    def test_floor_mark_node_visited(self):
        """Floor.mark_node_visited 正确更新状态"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)
        # 获取第一行一个可用节点
        available = [n for n in floor.get_available_nodes() if n.row == 0]
        assert len(available) > 0
        target = available[0]

        floor.mark_node_visited(target.node_id)

        # target 成为当前节点
        assert target.is_current is True
        assert target.visited is True
        assert target.is_cleared is True
        # 入口不再是当前节点
        entry = floor.get_node_by_id(floor.entry_node_id)
        assert entry.is_current is False
        # target 的连接节点变为 available
        for next_id in target.connections:
            next_node = floor.get_node_by_id(next_id)
            if next_node and not next_node.visited:
                assert next_node.available is True

    def test_floor_serialization(self):
        """Floor 可以完整序列化和反序列化"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)
        # 修改一些状态
        floor.mark_node_visited(floor.entry_node_id)

        d = floor.to_dict()
        restored = Floor.from_dict(d)

        assert restored.floor_number == floor.floor_number
        assert restored.entry_node_id == floor.entry_node_id
        assert restored.boss_node_id == floor.boss_node_id
        assert len(restored.nodes) == len(floor.nodes)
        assert restored.has_path_to_boss()

    def test_floor_has_path_to_boss(self):
        """Floor.has_path_to_boss BFS 验证连通性"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)
        assert floor.has_path_to_boss() is True

    def test_floor_count_paths_to_boss(self):
        """Floor.count_paths_to_boss 返回多条路径"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)
        paths = floor.count_paths_to_boss()
        # 标准地图至少有 2 条不同路径
        assert paths >= 2


class TestMapGenerationAlgorithm:
    """任务 4-2: 地图生成算法测试"""

    def test_node_count_in_range(self):
        """生成的内部节点数在 nodes_min ~ nodes_max 范围内"""
        for seed in range(20):
            gen = MapGenerator(random.Random(seed))
            floor = gen.generate_floor(1, STANDARD_CONFIG)
            interior = len(floor.nodes) - 2  # 去掉 entry 和 boss
            assert 8 <= interior <= 12, (
                f"seed={seed}: got {interior} nodes, expected 8-12"
            )

    def test_all_maps_have_path_to_boss(self):
        """100 个随机地图全部有从入口到 BOSS 的路径"""
        for seed in range(100):
            gen = MapGenerator(random.Random(seed))
            floor = gen.generate_floor(1, STANDARD_CONFIG)
            assert floor.has_path_to_boss(), f"seed={seed}: no path to boss"

    def test_room_type_weighted_distribution(self):
        """房间类型大致符合配置权重分布"""
        type_counts = {rt: 0 for rt in RoomType if rt != RoomType.BOSS and rt != RoomType.HIDDEN}
        total = 0
        for seed in range(50):
            gen = MapGenerator(random.Random(seed * 3))
            floor = gen.generate_floor(1, STANDARD_CONFIG)
            dist = gen.get_node_type_distribution(floor)
            for rt, count in dist.items():
                type_counts[rt] = type_counts.get(rt, 0) + count
                total += count

        # COMBAT 应该是最多的 (权重 50%)
        assert type_counts[RoomType.COMBAT] > type_counts[RoomType.ELITE]
        assert type_counts[RoomType.COMBAT] > type_counts[RoomType.REST]

    def test_no_rest_in_first_row(self):
        """第一行不出现 REST 节点"""
        for seed in range(50):
            gen = MapGenerator(random.Random(seed))
            floor = gen.generate_floor(1, STANDARD_CONFIG)
            first_row = floor.get_nodes_by_row(0)
            for node in first_row:
                assert node.room_type != RoomType.REST, (
                    f"seed={seed}: REST found in first row"
                )

    def test_last_row_has_rest_when_weighted(self):
        """BOSS 前最后一行保证至少一个 REST (当 rest 权重 > 0)"""
        rest_found_count = 0
        for seed in range(30):
            gen = MapGenerator(random.Random(seed))
            floor = gen.generate_floor(1, STANDARD_CONFIG)
            total_rows = floor.get_total_rows()
            last_row = floor.get_nodes_by_row(total_rows - 1)
            if any(n.room_type == RoomType.REST for n in last_row):
                rest_found_count += 1
        # 所有地图的最后一行都应有 REST
        assert rest_found_count == 30

    def test_render_coordinates_assigned(self):
        """所有节点都有非零渲染坐标"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)
        for node in floor.nodes:
            assert node.x > 0, f"node {node.node_id} has x=0"
            assert node.y > 0, f"node {node.node_id} has y=0"

    def test_small_floor_generation(self):
        """小地图 (4-5 节点) 也能正确生成"""
        for seed in range(30):
            gen = MapGenerator(random.Random(seed))
            floor = gen.generate_floor(5, SMALL_CONFIG)
            interior = len(floor.nodes) - 2
            assert 4 <= interior <= 5, f"seed={seed}: got {interior}"
            assert floor.has_path_to_boss(), f"seed={seed}: no path"

    def test_every_interior_node_reachable(self):
        """从入口出发 BFS 能到达所有内部节点"""
        gen = MapGenerator(random.Random(42))
        floor = gen.generate_floor(1, STANDARD_CONFIG)

        # BFS from entry
        from collections import deque
        visited = set()
        queue = deque([floor.entry_node_id])
        visited.add(floor.entry_node_id)
        while queue:
            nid = queue.popleft()
            node = floor.get_node_by_id(nid)
            if node:
                for next_id in node.connections:
                    if next_id not in visited:
                        visited.add(next_id)
                        queue.append(next_id)

        # 所有节点都应该被访问到
        all_ids = {n.node_id for n in floor.nodes}
        assert visited == all_ids, f"Unreachable nodes: {all_ids - visited}"

    def test_seed_determinism_with_config(self):
        """同种子 + 同配置生成相同地图 (含坐标)"""
        gen1 = MapGenerator(random.Random(777))
        gen2 = MapGenerator(random.Random(777))
        f1 = gen1.generate_floor(1, STANDARD_CONFIG)
        f2 = gen2.generate_floor(1, STANDARD_CONFIG)
        for n1, n2 in zip(f1.nodes, f2.nodes):
            assert n1.node_id == n2.node_id
            assert n1.room_type == n2.room_type
            assert n1.row == n2.row
            assert n1.col == n2.col
            assert n1.x == n2.x
            assert n1.y == n2.y
            assert n1.connections == n2.connections
