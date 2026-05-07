"""
地图导航场景单元测试
测试地图渲染逻辑、导航逻辑和房间进入逻辑 (不依赖 pygame 显示)
对应开发计划: 4-3, 4-4, 4-5
"""
import pytest
import random
from unittest.mock import MagicMock, patch

from src.scenes.map_navigation_scene import MapNavigationScene
from src.generation.map_generator import MapGenerator, MapNode, Floor
from src.utils.enums import GameState, RoomType


# ── 辅助 ──────────────────────────────────────────────────────────────────

def _make_floor(seed: int = 42) -> Floor:
    """生成一个标准测试楼层"""
    config = {
        "nodes_min": 8,
        "nodes_max": 12,
        "room_weights": {"combat": 50, "elite": 10, "shop": 15, "event": 15, "rest": 10}
    }
    rng = random.Random(seed)
    gen = MapGenerator(rng)
    return gen.generate_floor(1, config)


def _make_scene() -> MapNavigationScene:
    """创建一个 mock game 的场景实例"""
    mock_game = MagicMock()
    mock_game.state_machine = MagicMock()
    scene = MapNavigationScene(mock_game)
    return scene


# ═══════════════════════════════════════════════════════════════════════════════


class TestMapNavigation:
    """4-4: 地图导航逻辑测试"""

    def test_enter_generates_floor(self):
        """enter() 首次调用会生成楼层数据"""
        scene = _make_scene()
        scene.enter(character_id="knight", daily=False)
        assert scene._floor is not None
        assert scene._floor.has_path_to_boss()
        assert len(scene._floor.nodes) >= 6  # entry + interior + boss

    def test_enter_with_existing_floor(self):
        """enter() 可以接收已有楼层数据 (从战斗返回)"""
        scene = _make_scene()
        existing_floor = _make_floor(99)
        scene.enter(character_id="mage", floor=existing_floor, floor_number=2)
        assert scene._floor is existing_floor
        assert scene._floor_number == 2
        assert scene._character_id == "mage"

    def test_enter_daily_mode(self):
        """每日挑战模式设置正确"""
        scene = _make_scene()
        scene.enter(character_id="knight", daily=True)
        assert scene._daily_mode is True
        assert scene._floor is not None

    def test_initial_state_entry_is_current(self):
        """生成后入口节点是当前节点"""
        scene = _make_scene()
        scene.enter(character_id="knight")
        current = scene._floor.get_current_node()
        assert current is not None
        assert current.node_id == scene._floor.entry_node_id

    def test_first_row_nodes_available(self):
        """生成后第一行节点标记为可用"""
        scene = _make_scene()
        scene.enter(character_id="knight")
        available = scene._floor.get_available_nodes()
        # 过滤掉入口本身 (它 is_current + available)
        first_row = [n for n in available if n.row == 0]
        assert len(first_row) >= 2

    def test_get_node_at_hit_detection(self):
        """_get_node_at 正确检测鼠标位置"""
        scene = _make_scene()
        floor = _make_floor()
        scene._floor = floor

        # 精确命中第一个节点中心
        node = floor.nodes[1]  # 第一个普通节点 (跳过 entry)
        result = scene._get_node_at((int(node.x), int(node.y)))
        assert result is not None
        assert result.node_id == node.node_id

    def test_get_node_at_miss(self):
        """_get_node_at 对空白区域返回 None"""
        scene = _make_scene()
        floor = _make_floor()
        scene._floor = floor
        # 点击远离所有节点的位置
        result = scene._get_node_at((0, 0))
        assert result is None


class TestRoomEntry:
    """4-5: 房间进入逻辑测试"""

    def test_room_type_to_state_mapping(self):
        """所有房间类型都有对应的 GameState"""
        scene = _make_scene()
        assert scene._room_type_to_state(RoomType.COMBAT) == GameState.COMBAT
        assert scene._room_type_to_state(RoomType.ELITE) == GameState.COMBAT
        assert scene._room_type_to_state(RoomType.BOSS) == GameState.COMBAT
        assert scene._room_type_to_state(RoomType.SHOP) == GameState.SHOP
        assert scene._room_type_to_state(RoomType.EVENT) == GameState.EVENT
        assert scene._room_type_to_state(RoomType.REST) == GameState.REST

    def test_enter_node_updates_floor_state(self):
        """_enter_node 正确更新楼层状态"""
        scene = _make_scene()
        floor = _make_floor()
        scene._floor = floor
        scene._floor_number = 1
        scene._character_id = "knight"
        scene._daily_mode = False
        scene._seed = 42

        # 找一个可用节点
        available = [n for n in floor.get_available_nodes() if n.row == 0]
        assert len(available) > 0
        target = available[0]

        scene._enter_node(target)

        # 验证节点被标记为已访问
        assert target.visited is True
        assert target.is_cleared is True
        assert target.is_current is True

    def test_enter_node_triggers_state_change(self):
        """_enter_node 调用 state_machine.change 切换场景"""
        scene = _make_scene()
        floor = _make_floor()
        scene._floor = floor
        scene._floor_number = 1
        scene._character_id = "knight"
        scene._daily_mode = False
        scene._seed = 42

        available = [n for n in floor.get_available_nodes() if n.row == 0]
        target = available[0]

        scene._enter_node(target)

        # 验证 state_machine.change 被调用
        scene.game.state_machine.change.assert_called_once()
        call_args = scene.game.state_machine.change.call_args

        # 验证传入了正确的 GameState
        expected_state = scene._room_type_to_state(target.room_type)
        assert call_args[0][0] == expected_state

        # 验证传入了上下文
        kwargs = call_args[1]
        assert kwargs["floor"] is floor
        assert kwargs["floor_number"] == 1
        assert kwargs["character_id"] == "knight"
        assert kwargs["node_id"] == target.node_id
        assert kwargs["room_type"] == target.room_type

    def test_enter_combat_node(self):
        """进入战斗节点切换到 COMBAT 状态"""
        scene = _make_scene()
        floor = _make_floor(seed=100)
        scene._floor = floor
        scene._floor_number = 1
        scene._character_id = "knight"
        scene._daily_mode = False
        scene._seed = 100

        # 找到一个战斗类型的可用节点
        available = [n for n in floor.get_available_nodes() if n.row == 0]
        # 强制改为 COMBAT 类型来测试
        target = available[0]
        target.room_type = RoomType.COMBAT

        scene._enter_node(target)

        call_args = scene.game.state_machine.change.call_args
        assert call_args[0][0] == GameState.COMBAT

    def test_enter_shop_node(self):
        """进入商店节点切换到 SHOP 状态"""
        scene = _make_scene()
        floor = _make_floor(seed=200)
        scene._floor = floor
        scene._floor_number = 1
        scene._character_id = "knight"
        scene._daily_mode = False
        scene._seed = 200

        available = [n for n in floor.get_available_nodes() if n.row == 0]
        target = available[0]
        target.room_type = RoomType.SHOP

        scene._enter_node(target)

        call_args = scene.game.state_machine.change.call_args
        assert call_args[0][0] == GameState.SHOP

    def test_enter_event_node(self):
        """进入事件节点切换到 EVENT 状态"""
        scene = _make_scene()
        floor = _make_floor(seed=300)
        scene._floor = floor
        scene._floor_number = 1
        scene._character_id = "knight"
        scene._daily_mode = False
        scene._seed = 300

        available = [n for n in floor.get_available_nodes() if n.row == 0]
        target = available[0]
        target.room_type = RoomType.EVENT

        scene._enter_node(target)

        call_args = scene.game.state_machine.change.call_args
        assert call_args[0][0] == GameState.EVENT

    def test_enter_rest_node(self):
        """进入休息节点切换到 REST 状态"""
        scene = _make_scene()
        floor = _make_floor(seed=400)
        scene._floor = floor
        scene._floor_number = 1
        scene._character_id = "knight"
        scene._daily_mode = False
        scene._seed = 400

        available = [n for n in floor.get_available_nodes() if n.row == 0]
        target = available[0]
        target.room_type = RoomType.REST

        scene._enter_node(target)

        call_args = scene.game.state_machine.change.call_args
        assert call_args[0][0] == GameState.REST


class TestMapRendering:
    """4-3: 地图渲染逻辑测试 (不需要 pygame 窗口)"""

    def test_node_radius_by_type(self):
        """不同节点类型有不同的渲染半径"""
        scene = _make_scene()

        normal = MapNode(node_id=0, room_type=RoomType.COMBAT, row=0, col=0)
        boss = MapNode(node_id=1, room_type=RoomType.BOSS, row=5, col=0)
        entry = MapNode(node_id=2, room_type=RoomType.COMBAT, row=-1, col=0)

        r_normal = scene._get_node_radius(normal)
        r_boss = scene._get_node_radius(boss)
        r_entry = scene._get_node_radius(entry)

        # BOSS > normal > entry
        assert r_boss > r_normal
        assert r_normal > r_entry

    def test_dim_color(self):
        """_dim_color 正确减暗颜色"""
        result = MapNavigationScene._dim_color((100, 200, 50), 0.5)
        assert result == (50, 100, 25)

    def test_dim_color_zero(self):
        """_dim_color factor=0 返回全黑"""
        result = MapNavigationScene._dim_color((255, 255, 255), 0.0)
        assert result == (0, 0, 0)

    def test_all_room_types_have_styles(self):
        """所有非 HIDDEN 房间类型都有对应的渲染样式"""
        from src.scenes.map_navigation_scene import _NODE_STYLES
        for rt in [RoomType.COMBAT, RoomType.ELITE, RoomType.BOSS,
                   RoomType.SHOP, RoomType.EVENT, RoomType.REST]:
            assert rt in _NODE_STYLES, f"{rt.name} missing from _NODE_STYLES"
            bg, border, icon = _NODE_STYLES[rt]
            assert len(bg) == 3
            assert len(border) == 3
            assert len(icon) >= 1
