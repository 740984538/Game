"""
房间内容填充器
将生成的敌人列表转化为 ECS 实体
"""
from __future__ import annotations
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import esper
    from src.data.config_loader import ConfigLoader


class RoomPopulator:
    """负责将 DungeonGenerator 的结果实例化为 ECS 实体"""

    def __init__(self, config_loader: "ConfigLoader") -> None:
        self._config = config_loader

    def populate(
        self,
        world: "esper.World",
        spawns: List[Tuple[str, float, float]],
    ) -> List[int]:
        """
        :param world: ECS 世界
        :param spawns: [(enemy_id, x, y), ...]
        :return: 创建的实体 ID 列表
        """
        from src.ecs.entities import create_enemy
        entities = []
        all_enemies = self._config.load_all_enemies()
        for enemy_id, x, y in spawns:
            cfg = all_enemies.get(enemy_id)
            if cfg:
                eid = create_enemy(world, cfg, x, y)
                entities.append(eid)
        return entities
