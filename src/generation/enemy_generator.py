"""
敌人生成器 - 对应开发计划 6-14
根据楼层和战斗类型生成敌人。

完成标志:
  - 普通战斗生成1-3个普通敌人
  - 精英战斗生成1个精英敌人
  - BOSS战斗生成1个BOSS敌人
  - 敌人属性随楼层数递增
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, TYPE_CHECKING

from src.entities.enemies.enemy_data import EnemyData
from src.data.config_loader import ConfigLoader

if TYPE_CHECKING:
    pass


class EnemyGenerator:
    """
    敌人生成器。
    根据楼层编号和战斗类型（普通/精英/BOSS）生成对应的敌人列表。

    使用方式:
        generator = EnemyGenerator()
        enemies = generator.generate_combat(floor_number=3, room_type="combat")
        # enemies: List[EnemyData]

    对应文档 §4.2 战斗房间设计
    """

    def __init__(self, config_loader: Optional[ConfigLoader] = None,
                 seed: Optional[int] = None) -> None:
        self._config_loader = config_loader or ConfigLoader()
        self._seed = seed
        self._rng = random.Random(seed)

        # 缓存
        self._common_enemies: Optional[List[EnemyData]] = None
        self._elite_enemies: Optional[List[EnemyData]] = None
        self._boss_enemies: Optional[List[EnemyData]] = None

    # ─── 公开接口 ─────────────────────────────────────────────────────────

    def generate_combat(self, floor_number: int,
                        room_type: str = "combat") -> List[EnemyData]:
        """
        根据楼层和房间类型生成敌人列表。

        :param floor_number: 当前楼层编号 (1-based)
        :param room_type:    房间类型 ('combat' / 'elite' / 'boss')
        :return: 经过楼层缩放的 EnemyData 列表
        """
        if room_type == "boss":
            return self._generate_boss(floor_number)
        elif room_type == "elite":
            return self._generate_elite(floor_number)
        else:
            return self._generate_normal(floor_number)

    def generate_for_node(self, floor_number: int,
                          room_type: str, node_id: int = 0) -> List[EnemyData]:
        """
        为地图节点生成敌人（带节点 ID 用于确定性）。
        """
        # 使用节点ID影响随机种子，确保同一种子同一节点生成相同敌人
        if self._seed is not None:
            node_seed = self._seed + node_id * 1000 + floor_number * 100
            self._rng = random.Random(node_seed)

        return self.generate_combat(floor_number, room_type)

    # ─── 普通战斗生成 ─────────────────────────────────────────────────────

    def _generate_normal(self, floor_number: int) -> List[EnemyData]:
        """
        普通战斗：生成 1-3 个普通敌人。
        高楼层倾向于生成更多敌人。
        """
        common_pool = self._get_common_enemies()
        if not common_pool:
            return []

        # 敌人数量: 1-3，楼层越高越可能多
        min_count = 1
        max_count = min(3, 1 + floor_number // 3)
        count = self._rng.randint(min_count, max(min_count, max_count))

        enemies: List[EnemyData] = []
        for _ in range(count):
            base_enemy = self._rng.choice(common_pool)
            # 根据楼层缩放属性
            scaled = base_enemy.scale_for_floor(floor_number)
            enemies.append(scaled)

        return enemies

    # ─── 精英战斗生成 ─────────────────────────────────────────────────────

    def _generate_elite(self, floor_number: int) -> List[EnemyData]:
        """
        精英战斗：生成 1 个精英敌人。
        """
        elite_pool = self._get_elite_enemies()
        if not elite_pool:
            # 如果没有精英配置，用强化的普通敌人替代
            common_pool = self._get_common_enemies()
            if not common_pool:
                return []
            base = self._rng.choice(common_pool)
            scaled = base.scale_for_floor(floor_number + 3)  # 额外加3层难度
            return [scaled]

        base_enemy = self._rng.choice(elite_pool)
        scaled = base_enemy.scale_for_floor(floor_number)
        return [scaled]

    # ─── BOSS 战斗生成 ────────────────────────────────────────────────────

    def _generate_boss(self, floor_number: int) -> List[EnemyData]:
        """
        BOSS战斗：生成 1 个 BOSS 敌人。
        优先选择对应楼层的 BOSS，否则随机。
        """
        boss_pool = self._get_boss_enemies()
        if not boss_pool:
            # 退化为精英
            return self._generate_elite(floor_number)

        # 尝试找到对应楼层的 BOSS
        floor_boss = [b for b in boss_pool if b.floor == floor_number]
        if floor_boss:
            base_enemy = self._rng.choice(floor_boss)
        else:
            base_enemy = self._rng.choice(boss_pool)

        # BOSS 通常不按普通公式缩放，但可以轻微增强
        scaled = base_enemy.scale_for_floor(max(1, floor_number // 2))
        return [scaled]

    # ─── 敌人池加载 ──────────────────────────────────────────────────────

    def _get_common_enemies(self) -> List[EnemyData]:
        """获取普通敌人池"""
        if self._common_enemies is None:
            self._load_enemy_pools()
        return self._common_enemies or []

    def _get_elite_enemies(self) -> List[EnemyData]:
        """获取精英敌人池"""
        if self._elite_enemies is None:
            self._load_enemy_pools()
        return self._elite_enemies or []

    def _get_boss_enemies(self) -> List[EnemyData]:
        """获取BOSS敌人池"""
        if self._boss_enemies is None:
            self._load_enemy_pools()
        return self._boss_enemies or []

    def _load_enemy_pools(self) -> None:
        """从配置加载并分类所有敌人"""
        all_configs = self._config_loader.load_all_enemies()

        self._common_enemies = []
        self._elite_enemies = []
        self._boss_enemies = []

        for enemy_id, config in all_configs.items():
            enemy_data = EnemyData.from_config(config)
            enemy_type = enemy_data.enemy_type

            if enemy_type == "common":
                self._common_enemies.append(enemy_data)
            elif enemy_type == "elite":
                self._elite_enemies.append(enemy_data)
            elif enemy_type == "boss":
                self._boss_enemies.append(enemy_data)

    # ─── 工具方法 ─────────────────────────────────────────────────────────

    def set_seed(self, seed: int) -> None:
        """设置随机种子"""
        self._seed = seed
        self._rng = random.Random(seed)

    def get_enemy_configs(self, enemies: List[EnemyData]) -> List[Dict]:
        """
        将 EnemyData 列表转换为 EntityFactory 可用的配置字典列表。
        """
        return [enemy.to_entity_config() for enemy in enemies]
