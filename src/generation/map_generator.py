"""
地图生成器 - 对应文档 §4.1 / §8.3.2 / §10.4.1
基于图论算法生成楼层节点地图
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from src.utils.enums import RoomType


@dataclass
class MapNode:
    """地图节点，代表一个房间入口"""
    node_id: int
    room_type: RoomType
    row: int
    col: int
    connections: List[int] = field(default_factory=list)  # 连通的下一层节点ID
    visited: bool = False
    available: bool = False


@dataclass
class Floor:
    """单层楼层数据"""
    floor_number: int
    nodes: List[MapNode]
    entry_node_id: int
    boss_node_id: int


class MapGenerator:
    """
    楼层地图生成器。
    算法：按行（排）生成节点，每排随机决定节点数，
    相邻排之间建立连接，确保从入口到BOSS有多条路径。
    对应文档 §4.1.3 地图生成规则
    """

    # 每排节点数
    _NODES_PER_ROW = (2, 3, 4)
    # 行数（不含入口和BOSS行）
    _ROWS = 5

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._next_id = 0

    def _new_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def generate_floor(self, floor_number: int, floor_config: dict) -> Floor:
        """
        生成完整楼层地图
        :param floor_number: 层数 (1-5)
        :param floor_config: 对应 config/levels/floor_N.yaml
        """
        self._next_id = 0
        rows: List[List[MapNode]] = []

        # 生成每排节点
        for row_idx in range(self._ROWS):
            count = self._rng.choice(self._NODES_PER_ROW)
            row = []
            for col in range(count):
                room_type = self._pick_room_type(floor_config, row_idx)
                node = MapNode(
                    node_id=self._new_id(),
                    room_type=room_type,
                    row=row_idx,
                    col=col,
                )
                row.append(node)
            rows.append(row)

        # 建立连接（上一排每节点向下一排1-2个节点连线）
        for row_idx in range(len(rows) - 1):
            for node in rows[row_idx]:
                targets = self._rng.sample(rows[row_idx + 1],
                                           k=min(2, len(rows[row_idx + 1])))
                for t in targets:
                    if t.node_id not in node.connections:
                        node.connections.append(t.node_id)

        # 入口节点（虚拟，连接第一排所有节点）
        entry = MapNode(node_id=self._new_id(), room_type=RoomType.COMBAT,
                        row=-1, col=0)
        entry.connections = [n.node_id for n in rows[0]]
        entry.available = True

        # BOSS节点
        boss = MapNode(node_id=self._new_id(), room_type=RoomType.BOSS,
                       row=self._ROWS, col=0)
        for node in rows[-1]:
            node.connections.append(boss.node_id)

        all_nodes = [entry] + [n for row in rows for n in row] + [boss]
        return Floor(
            floor_number=floor_number,
            nodes=all_nodes,
            entry_node_id=entry.node_id,
            boss_node_id=boss.node_id,
        )

    def _pick_room_type(self, floor_config: dict, row_idx: int) -> RoomType:
        """根据权重随机选择房间类型"""
        weights_cfg = floor_config.get("room_weights", {})
        options = {
            RoomType.COMBAT: weights_cfg.get("combat", 50),
            RoomType.ELITE:  weights_cfg.get("elite", 10),
            RoomType.SHOP:   weights_cfg.get("shop", 15),
            RoomType.EVENT:  weights_cfg.get("event", 15),
            RoomType.REST:   weights_cfg.get("rest", 10),
        }
        types = list(options.keys())
        weights = list(options.values())
        return self._rng.choices(types, weights=weights, k=1)[0]
