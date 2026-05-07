"""
地图生成器 - 对应文档 §4.1 / §8.3.2 / §10.4.1
基于图论算法生成楼层节点地图

任务 4-1: 地图节点数据结构
任务 4-2: 地图生成算法
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple

from src.utils.enums import RoomType


# ============================================================
# 任务 4-1: 地图节点数据结构
# ============================================================

@dataclass
class MapNode:
    """
    地图节点，代表一个可访问的房间入口。

    属性说明:
        node_id:     节点唯一标识
        room_type:   房间类型 (战斗/精英/BOSS/商店/事件/休息)
        row:         节点所在逻辑行 (0-based; -1=入口, 最大行+1=BOSS)
        col:         节点在本行中的逻辑列
        x:           在地图画面上的渲染 X 坐标 (像素)
        y:           在地图画面上的渲染 Y 坐标 (像素)
        connections: 该节点指向的后续节点 ID 列表 (有向边: 当前 → 下一层)
        visited:     玩家是否已经到达过该节点
        available:   当前是否可以点击进入 (与当前节点相连的下一批节点)
        is_cleared:  该房间是否已经被清理/完成
        is_current:  是否是玩家当前所在节点
    """
    node_id: int
    room_type: RoomType
    row: int
    col: int
    # 渲染坐标 (由 layout 阶段计算, 生成时为 0.0)
    x: float = 0.0
    y: float = 0.0
    # 连接关系
    connections: List[int] = field(default_factory=list)
    # 状态
    visited: bool = False
    available: bool = False
    is_cleared: bool = False
    is_current: bool = False

    def to_dict(self) -> dict:
        """序列化为字典，用于存档"""
        return {
            "node_id": self.node_id,
            "room_type": self.room_type.value,
            "row": self.row,
            "col": self.col,
            "x": self.x,
            "y": self.y,
            "connections": self.connections[:],
            "visited": self.visited,
            "available": self.available,
            "is_cleared": self.is_cleared,
            "is_current": self.is_current,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapNode":
        """从字典反序列化"""
        return cls(
            node_id=data["node_id"],
            room_type=RoomType(data["room_type"]),
            row=data["row"],
            col=data["col"],
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            connections=data.get("connections", []),
            visited=data.get("visited", False),
            available=data.get("available", False),
            is_cleared=data.get("is_cleared", False),
            is_current=data.get("is_current", False),
        )


@dataclass
class Floor:
    """
    单层楼层数据，包含所有节点和辅助查询方法。

    属性说明:
        floor_number:  楼层编号 (1-based)
        nodes:         本层所有节点列表
        entry_node_id: 入口节点 ID
        boss_node_id:  BOSS 节点 ID
    """
    floor_number: int
    nodes: List[MapNode] = field(default_factory=list)
    entry_node_id: int = 0
    boss_node_id: int = 0

    # -- 辅助查询方法 --

    def get_node_by_id(self, node_id: int) -> Optional[MapNode]:
        """根据 ID 获取节点，不存在返回 None"""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_nodes_by_row(self, row: int) -> List[MapNode]:
        """获取指定行的所有节点"""
        return [n for n in self.nodes if n.row == row]

    def get_nodes_by_type(self, room_type: RoomType) -> List[MapNode]:
        """获取指定类型的所有节点"""
        return [n for n in self.nodes if n.room_type == room_type]

    def get_available_nodes(self) -> List[MapNode]:
        """获取当前可移动到的节点"""
        return [n for n in self.nodes if n.available]

    def get_current_node(self) -> Optional[MapNode]:
        """获取玩家当前所在节点"""
        for n in self.nodes:
            if n.is_current:
                return n
        return None

    def get_entry_node(self) -> Optional[MapNode]:
        """获取入口节点"""
        return self.get_node_by_id(self.entry_node_id)

    def get_boss_node(self) -> Optional[MapNode]:
        """获取 BOSS 节点"""
        return self.get_node_by_id(self.boss_node_id)

    def get_total_rows(self) -> int:
        """获取地图总行数（不含入口和BOSS行）"""
        normal_rows = [n.row for n in self.nodes if n.row >= 0
                       and n.room_type != RoomType.BOSS]
        return max(normal_rows) + 1 if normal_rows else 0

    def has_path_to_boss(self) -> bool:
        """BFS 验证从入口到 BOSS 是否有连通路径"""
        if not self.nodes:
            return False
        visited: Set[int] = set()
        queue = deque([self.entry_node_id])
        visited.add(self.entry_node_id)
        while queue:
            current_id = queue.popleft()
            if current_id == self.boss_node_id:
                return True
            node = self.get_node_by_id(current_id)
            if node is None:
                continue
            for next_id in node.connections:
                if next_id not in visited:
                    visited.add(next_id)
                    queue.append(next_id)
        return False

    def count_paths_to_boss(self) -> int:
        """
        DFS 计算从入口到 BOSS 的不同路径数量。
        用于验证地图分支丰富度。
        """
        count = 0

        def dfs(node_id: int, path_visited: Set[int]):
            nonlocal count
            if node_id == self.boss_node_id:
                count += 1
                return
            node = self.get_node_by_id(node_id)
            if node is None:
                return
            for next_id in node.connections:
                if next_id not in path_visited:
                    path_visited.add(next_id)
                    dfs(next_id, path_visited)
                    path_visited.discard(next_id)

        dfs(self.entry_node_id, {self.entry_node_id})
        return count

    def mark_node_visited(self, node_id: int) -> None:
        """标记节点为已访问，并更新可用状态"""
        node = self.get_node_by_id(node_id)
        if node is None:
            return
        # 清除旧 current
        for n in self.nodes:
            n.is_current = False
            n.available = False
        # 标记新状态
        node.visited = True
        node.is_cleared = True
        node.is_current = True
        # 标记可达节点
        for next_id in node.connections:
            next_node = self.get_node_by_id(next_id)
            if next_node and not next_node.visited:
                next_node.available = True

    def to_dict(self) -> dict:
        """序列化整层数据"""
        return {
            "floor_number": self.floor_number,
            "nodes": [n.to_dict() for n in self.nodes],
            "entry_node_id": self.entry_node_id,
            "boss_node_id": self.boss_node_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Floor":
        """从字典反序列化"""
        floor = cls(
            floor_number=data["floor_number"],
            entry_node_id=data["entry_node_id"],
            boss_node_id=data["boss_node_id"],
        )
        floor.nodes = [MapNode.from_dict(nd) for nd in data.get("nodes", [])]
        return floor


# ============================================================
# 任务 4-2: 地图生成算法
# ============================================================

class MapGenerator:
    """
    楼层地图生成器。

    算法概要（类 Slay the Spire 风格）:
    1. 根据配置确定总节点数 (nodes_min ~ nodes_max, 默认 8-12)
    2. 将节点分布到多个行中 (每行 2-4 个节点)
    3. 相邻行之间建立有向连接 (每个节点至少连 1 个下层节点)
    4. 添加入口节点 (连到第一行所有节点) 和 BOSS 节点 (最后一行都连向它)
    5. BFS 验证从入口到 BOSS 连通性
    6. 按配置权重分配房间类型 (含约束: 休息节点不出现在第一行, BOSS 前行必有休息)
    7. 计算各节点的屏幕渲染坐标

    对应文档 §4.1.3 地图生成规则
    """

    # 默认参数 (被 floor_config 覆盖)
    _DEFAULT_NODES_MIN = 8
    _DEFAULT_NODES_MAX = 12
    _DEFAULT_NODES_PER_ROW_MIN = 2
    _DEFAULT_NODES_PER_ROW_MAX = 4

    # 渲染布局参数
    _MAP_PADDING_X = 120   # 左右边距
    _MAP_PADDING_Y = 80    # 上下边距
    _MAP_WIDTH = 1040      # 有效绘图宽度 (1280 - 2*120)
    _MAP_HEIGHT = 560      # 有效绘图高度 (720 - 2*80)

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._next_id = 0

    def _new_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def generate_floor(self, floor_number: int, floor_config: dict) -> Floor:
        """
        生成完整楼层地图。

        :param floor_number: 层数 (1-based)
        :param floor_config: 对应 config/levels/floor_N.yaml 的 floor 字段内容
        :return: 生成好的 Floor 对象
        """
        self._next_id = 0

        # 1. 确定节点数量和行分布
        nodes_min = floor_config.get("nodes_min", self._DEFAULT_NODES_MIN)
        nodes_max = floor_config.get("nodes_max", self._DEFAULT_NODES_MAX)
        total_nodes = self._rng.randint(nodes_min, nodes_max)

        rows = self._distribute_nodes_to_rows(total_nodes)
        num_rows = len(rows)

        # 2. 为每行创建节点 (先临时分配 COMBAT 类型, 后面再重新分配)
        node_rows: List[List[MapNode]] = []
        for row_idx, row_count in enumerate(rows):
            row_nodes = []
            for col in range(row_count):
                node = MapNode(
                    node_id=self._new_id(),
                    room_type=RoomType.COMBAT,  # 占位, 后面重新分配
                    row=row_idx,
                    col=col,
                )
                row_nodes.append(node)
            node_rows.append(row_nodes)

        # 3. 建立相邻行之间的连接
        self._connect_rows(node_rows)

        # 4. 创建入口节点
        entry = MapNode(
            node_id=self._new_id(),
            room_type=RoomType.COMBAT,
            row=-1,
            col=0,
        )
        entry.connections = [n.node_id for n in node_rows[0]]
        entry.available = True
        entry.visited = True
        entry.is_current = True

        # 5. 创建 BOSS 节点
        boss = MapNode(
            node_id=self._new_id(),
            room_type=RoomType.BOSS,
            row=num_rows,
            col=0,
        )
        for node in node_rows[-1]:
            node.connections.append(boss.node_id)

        # 6. 组装所有节点
        all_nodes = [entry]
        for row_nodes in node_rows:
            all_nodes.extend(row_nodes)
        all_nodes.append(boss)

        # 7. 分配房间类型 (入口和 BOSS 不参与)
        interior_nodes = [n for n in all_nodes
                         if n.node_id != entry.node_id
                         and n.node_id != boss.node_id]
        self._assign_room_types(interior_nodes, floor_config, num_rows)

        # 8. 构建 Floor 对象
        floor = Floor(
            floor_number=floor_number,
            nodes=all_nodes,
            entry_node_id=entry.node_id,
            boss_node_id=boss.node_id,
        )

        # 9. 验证连通性 (保障性检查, 不通过则补边)
        if not floor.has_path_to_boss():
            self._ensure_connectivity(node_rows, boss.node_id)

        # 10. 计算渲染坐标
        self._compute_layout(floor, num_rows)

        # 11. 设置第一行节点为可用
        for n in node_rows[0]:
            n.available = True

        return floor

    # ----------------------------------------------------------
    # 私有方法: 节点分布
    # ----------------------------------------------------------

    def _distribute_nodes_to_rows(self, total_nodes: int) -> List[int]:
        """
        将 total_nodes 个节点分配到若干行中。
        每行 1-4 个节点，行数自适应。
        对于小地图 (< 6 节点) 允许每行最少 1 个节点和 2 行。
        对于标准地图 (>= 6 节点) 确保至少 3 行, 每行 2-4 个节点。
        """
        # 小地图特殊处理 (如 floor_5 只有 4-5 个节点)
        if total_nodes <= 5:
            return self._distribute_small(total_nodes)

        # 标准地图: 确保至少 3 行
        min_rows = 3
        rows: List[int] = []
        remaining = total_nodes

        while remaining > 0:
            rows_left = max(1, min_rows - len(rows))
            if remaining <= self._DEFAULT_NODES_PER_ROW_MAX and rows_left <= 1:
                rows.append(remaining)
                remaining = 0
            else:
                # 确保剩余节点够分给后续行
                max_this = min(
                    self._DEFAULT_NODES_PER_ROW_MAX,
                    remaining - (rows_left - 1) * self._DEFAULT_NODES_PER_ROW_MIN
                    if rows_left > 1 else remaining
                )
                min_this = max(
                    self._DEFAULT_NODES_PER_ROW_MIN,
                    remaining - (rows_left - 1) * self._DEFAULT_NODES_PER_ROW_MAX
                    if rows_left > 1 else remaining
                )
                # 安全钳位
                min_this = max(1, min(min_this, max_this))
                max_this = max(min_this, max_this)

                count = self._rng.randint(min_this, max_this)
                rows.append(count)
                remaining -= count

        return rows

    def _distribute_small(self, total_nodes: int) -> List[int]:
        """小地图分配 (节点数 <= 5): 允许每行 1 个节点, 至少 2 行"""
        if total_nodes <= 2:
            return [1] * total_nodes
        if total_nodes <= 3:
            return [1, 2] if self._rng.random() < 0.5 else [2, 1]

        # 4-5 个节点: 分 2-3 行
        num_rows = self._rng.randint(2, min(3, total_nodes - 1))
        rows: List[int] = []
        remaining = total_nodes
        for i in range(num_rows):
            if i == num_rows - 1:
                rows.append(remaining)
            else:
                max_this = min(3, remaining - (num_rows - i - 1))
                count = self._rng.randint(1, max(1, max_this))
                rows.append(count)
                remaining -= count
        return rows

    # ----------------------------------------------------------
    # 私有方法: 连接建立
    # ----------------------------------------------------------

    def _connect_rows(self, node_rows: List[List[MapNode]]) -> None:
        """
        为相邻行之间建立有向连接。

        规则:
        - 每个上层节点至少连接 1 个下层节点 (保证不出现死路)
        - 每个下层节点至少被 1 个上层节点连接 (保证可达性)
        - 在满足上述约束后，随机添加额外连接以增加路径多样性
        """
        for row_idx in range(len(node_rows) - 1):
            upper = node_rows[row_idx]
            lower = node_rows[row_idx + 1]

            # 阶段 1: 确保每个下层节点至少有一个入边
            for lower_node in lower:
                source = self._rng.choice(upper)
                if lower_node.node_id not in source.connections:
                    source.connections.append(lower_node.node_id)

            # 阶段 2: 确保每个上层节点至少有一条出边
            for upper_node in upper:
                if not upper_node.connections:
                    target = self._rng.choice(lower)
                    upper_node.connections.append(target.node_id)

            # 阶段 3: 随机添加额外连接 (增加路径分支)
            extra_edges = self._rng.randint(1, max(1, len(upper) // 2))
            for _ in range(extra_edges):
                src = self._rng.choice(upper)
                dst = self._rng.choice(lower)
                if dst.node_id not in src.connections:
                    src.connections.append(dst.node_id)

    def _ensure_connectivity(self, node_rows: List[List[MapNode]],
                             boss_node_id: int) -> None:
        """
        兜底: 如果 BFS 检测不连通, 在最后一行节点与 BOSS 之间补边。
        (正常情况下不会触发, 因为 _connect_rows 已保证连通)
        """
        for node in node_rows[-1]:
            if boss_node_id not in node.connections:
                node.connections.append(boss_node_id)

    # ----------------------------------------------------------
    # 私有方法: 房间类型分配
    # ----------------------------------------------------------

    def _assign_room_types(self, nodes: List[MapNode],
                           floor_config: dict, num_rows: int) -> None:
        """
        按配置权重随机分配房间类型，附带以下约束:
        - 第一行不出现 REST 和 SHOP (玩家刚进入楼层)
        - BOSS 前一行保证至少有一个 REST 节点 (给玩家喘息机会)
        - ELITE 节点不出现在第一行
        """
        weights_cfg = floor_config.get("room_weights", {})

        # 基础权重
        base_weights = {
            RoomType.COMBAT: weights_cfg.get("combat", 50),
            RoomType.ELITE: weights_cfg.get("elite", 10),
            RoomType.SHOP: weights_cfg.get("shop", 15),
            RoomType.EVENT: weights_cfg.get("event", 15),
            RoomType.REST: weights_cfg.get("rest", 10),
        }

        # 按行分组
        rows_map: Dict[int, List[MapNode]] = {}
        for node in nodes:
            rows_map.setdefault(node.row, []).append(node)

        last_row_idx = num_rows - 1

        # 先处理约束: BOSS 前一行保证一个 REST
        if last_row_idx in rows_map and base_weights.get(RoomType.REST, 0) > 0:
            last_row_nodes = rows_map[last_row_idx]
            rest_candidate = self._rng.choice(last_row_nodes)
            rest_candidate.room_type = RoomType.REST

        # 分配其余节点
        for node in nodes:
            # 已被约束分配的节点跳过
            if node.room_type == RoomType.REST and node.row == last_row_idx:
                continue

            # 第一行约束
            if node.row == 0:
                constrained_weights = {
                    k: v for k, v in base_weights.items()
                    if k not in (RoomType.REST, RoomType.SHOP, RoomType.ELITE)
                }
            else:
                constrained_weights = base_weights.copy()

            # 如果权重全为 0, 默认战斗
            if sum(constrained_weights.values()) == 0:
                node.room_type = RoomType.COMBAT
                continue

            types = list(constrained_weights.keys())
            weights = list(constrained_weights.values())
            node.room_type = self._rng.choices(types, weights=weights, k=1)[0]

    # ----------------------------------------------------------
    # 私有方法: 渲染坐标计算
    # ----------------------------------------------------------

    def _compute_layout(self, floor: Floor, num_rows: int) -> None:
        """
        为每个节点计算屏幕渲染坐标。
        节点按行均匀纵向分布，行内均匀横向分布并加入小量抖动。
        """
        # 有效区域
        x_start = self._MAP_PADDING_X
        y_start = self._MAP_PADDING_Y
        usable_w = self._MAP_WIDTH
        usable_h = self._MAP_HEIGHT

        # 总逻辑行数包含入口行(-1)和 BOSS 行(num_rows)
        total_visual_rows = num_rows + 2  # entry + normal rows + boss
        row_spacing = usable_h / max(1, total_visual_rows - 1)

        for node in floor.nodes:
            # 计算 Y 坐标 (入口在顶部, BOSS在底部)
            visual_row = node.row + 1  # -1 → 0, 0 → 1, ..., num_rows → num_rows+1
            node.y = y_start + visual_row * row_spacing

            # 计算 X 坐标 (行内均匀分布)
            same_row = floor.get_nodes_by_row(node.row)
            count_in_row = len(same_row)
            if count_in_row == 1:
                node.x = x_start + usable_w / 2
            else:
                col_spacing = usable_w / (count_in_row + 1)
                node.x = x_start + col_spacing * (node.col + 1)

            # 加入小量随机抖动 (避免过于整齐), BOSS 和入口不抖动
            if node.row >= 0 and node.room_type != RoomType.BOSS:
                node.x += self._rng.uniform(-15, 15)
                node.y += self._rng.uniform(-8, 8)

    # ----------------------------------------------------------
    # 公开辅助方法
    # ----------------------------------------------------------

    def get_node_type_distribution(self, floor: Floor) -> Dict[RoomType, int]:
        """统计楼层各类型节点数量 (不含入口和BOSS)"""
        dist: Dict[RoomType, int] = {}
        for node in floor.nodes:
            if node.row >= 0 and node.room_type != RoomType.BOSS:
                dist[node.room_type] = dist.get(node.room_type, 0) + 1
        return dist
