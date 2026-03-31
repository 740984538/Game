"""
地牢房间生成器 - 对应文档 §4.2 战斗房间设计
根据房间类型和层数生成房间内部布局（敌人位置、障碍物）
"""
from __future__ import annotations
import random
from typing import List, Tuple
from src.utils.enums import RoomType


@dataclass_placeholder = None  # 占位，避免循环引用


class DungeonGenerator:
    """
    生成单个房间内部的实体布局。
    - 普通战斗房间：3-6只普通怪，随机分布
    - 精英战斗房间：1只精英+2-4只普通怪
    - BOSS房间：单个BOSS居中
    对应文档 §4.2.1 / §4.2.2 / §4.2.3
    """

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def generate_enemy_positions(
        self,
        room_type: RoomType,
        floor_number: int,
        enemy_pool: List[str],
        elite_pool: List[str],
        boss_id: str,
        room_width: int = 800,
        room_height: int = 500,
    ) -> List[Tuple[str, float, float]]:
        """
        返回 [(enemy_id, x, y), ...] 列表
        """
        margin = 80
        spawns = []

        if room_type == RoomType.COMBAT:
            count = self._rng.randint(3, 6)
            for _ in range(count):
                eid = self._rng.choice(enemy_pool)
                x = self._rng.uniform(margin, room_width - margin)
                y = self._rng.uniform(margin, room_height - margin)
                spawns.append((eid, x, y))

        elif room_type == RoomType.ELITE:
            elite_id = self._rng.choice(elite_pool)
            spawns.append((elite_id, room_width / 2, room_height / 2))
            for _ in range(self._rng.randint(2, 4)):
                eid = self._rng.choice(enemy_pool)
                x = self._rng.uniform(margin, room_width - margin)
                y = self._rng.uniform(margin, room_height - margin)
                spawns.append((eid, x, y))

        elif room_type == RoomType.BOSS:
            spawns.append((boss_id, room_width / 2, room_height / 3))

        return spawns
