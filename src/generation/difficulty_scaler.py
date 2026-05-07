"""
难度缩放器 - 对应开发计划 8-10 (游戏难度曲线)，文档 §3.1.4 / §4.1.2

提供：
  - DifficultyScaler 类：根据楼层数和全局难度系数缩放
      - 敌人 HP / 攻击力 / 防御
      - 商店物品价格
      - 遗物掉落概率
      - 精英敌人比例

设计准则：
  - "纵向缩放"按楼层（1~5），HP +10%/层、攻击 +8%/层、防御 +5%/层
  - "横向缩放"按全局难度（0~4），从 game_config.yaml 的 difficulty_modifiers 节读取
  - 商店价格按楼层 +15%/层，难度 +20%/级
  - 精英比例按楼层 +5%（线性）

最终缩放系数 = 楼层缩放 × 难度缩放
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 默认难度配置（与 config/game_config.yaml 同步）
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_DIFFICULTY_MODIFIERS: Dict[int, Dict[str, Any]] = {
    0: {"name": "新手",  "enemy_hp_mult": 1.0, "enemy_atk_mult": 1.0, "revive_count": 1},
    1: {"name": "普通",  "enemy_hp_mult": 1.2, "enemy_atk_mult": 1.0, "revive_count": 0},
    2: {"name": "困难",  "enemy_hp_mult": 1.5, "enemy_atk_mult": 1.2, "revive_count": 0},
    3: {"name": "噩梦",  "enemy_hp_mult": 2.0, "enemy_atk_mult": 1.5, "revive_count": 0},
    4: {"name": "地狱",  "enemy_hp_mult": 3.0, "enemy_atk_mult": 2.0, "revive_count": 0},
}

# 楼层基础递增系数（每升 1 层叠加）
FLOOR_HP_PER_LEVEL: float = 0.10
FLOOR_ATK_PER_LEVEL: float = 0.08
FLOOR_DEF_PER_LEVEL: float = 0.05

# 商店价格缩放
SHOP_PRICE_FLOOR_MULT: float = 0.15      # 每层 +15%
SHOP_PRICE_DIFFICULTY_MULT: float = 0.20  # 每级难度 +20%

# 精英比例：基础 10%，每层 +5%，最高 35%
ELITE_BASE_RATIO: float = 0.10
ELITE_PER_FLOOR: float = 0.05
ELITE_MAX_RATIO: float = 0.35

# 遗物掉落概率（普通战斗）
RELIC_BASE_DROP_CHANCE: float = 0.30
RELIC_DROP_FLOOR_BONUS: float = 0.05      # 每层 +5%
RELIC_DROP_MAX: float = 0.60


# ═══════════════════════════════════════════════════════════════════════════════
# 数据载体
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScaledStats:
    """缩放后的敌人属性"""
    health: int
    attack: int
    defense: int


# ═══════════════════════════════════════════════════════════════════════════════
# DifficultyScaler
# ═══════════════════════════════════════════════════════════════════════════════

class DifficultyScaler:
    """
    封装所有难度相关的缩放计算。
    无状态：所有方法均接收楼层号 + 难度作为参数。
    """

    def __init__(self,
                 difficulty_modifiers: Optional[Dict[int, Dict[str, Any]]] = None) -> None:
        self._modifiers: Dict[int, Dict[str, Any]] = (
            difficulty_modifiers or dict(_DEFAULT_DIFFICULTY_MODIFIERS)
        )

    # ── 工厂方法 ──────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config_path: str = "config") -> "DifficultyScaler":
        """从 config/game_config.yaml 读取 difficulty_modifiers 节"""
        try:
            from src.data.config_loader import ConfigLoader
            cfg = ConfigLoader(config_path).load_game_config()
            mods = cfg.get("difficulty_modifiers")
            if mods:
                # YAML 的整数 key 在 PyYAML 中保持为 int
                normalized = {int(k): v for k, v in mods.items()}
                return cls(normalized)
        except Exception as exc:
            logger.warning("加载难度配置失败: %s, 使用默认值", exc)
        return cls()

    # ── 难度数据访问 ──────────────────────────────────────────────────────

    def get_difficulty_name(self, difficulty: int) -> str:
        return self._modifiers.get(difficulty, {}).get("name", f"难度{difficulty}")

    def get_revive_count(self, difficulty: int) -> int:
        return int(self._modifiers.get(difficulty, {}).get("revive_count", 0))

    # ── 敌人缩放 ──────────────────────────────────────────────────────────

    def floor_hp_mult(self, floor: int) -> float:
        """单纯按楼层的 HP 缩放系数（不含难度）"""
        return 1.0 + max(0, floor - 1) * FLOOR_HP_PER_LEVEL

    def floor_atk_mult(self, floor: int) -> float:
        return 1.0 + max(0, floor - 1) * FLOOR_ATK_PER_LEVEL

    def floor_def_mult(self, floor: int) -> float:
        return 1.0 + max(0, floor - 1) * FLOOR_DEF_PER_LEVEL

    def difficulty_hp_mult(self, difficulty: int) -> float:
        return float(self._modifiers.get(difficulty, {}).get("enemy_hp_mult", 1.0))

    def difficulty_atk_mult(self, difficulty: int) -> float:
        return float(self._modifiers.get(difficulty, {}).get("enemy_atk_mult", 1.0))

    def scale_enemy_stats(self, base_health: int, base_attack: int,
                          base_defense: int,
                          floor: int = 1, difficulty: int = 1) -> ScaledStats:
        """
        综合楼层 + 难度缩放敌人属性。
        """
        hp_mult = self.floor_hp_mult(floor) * self.difficulty_hp_mult(difficulty)
        atk_mult = self.floor_atk_mult(floor) * self.difficulty_atk_mult(difficulty)
        def_mult = self.floor_def_mult(floor)  # 防御不受难度影响

        return ScaledStats(
            health=max(1, int(base_health * hp_mult)),
            attack=max(1, int(base_attack * atk_mult)),
            defense=max(0, int(base_defense * def_mult)),
        )

    def scale_enemy_config(self, enemy_config: dict,
                           floor: int = 1, difficulty: int = 1) -> dict:
        """
        对 EntityFactory 使用的 enemy_config dict 进行就地缩放（返回新字典）。
        """
        import copy
        scaled = copy.deepcopy(enemy_config)
        base = scaled.get("base_stats", {})
        result = self.scale_enemy_stats(
            base.get("health", 30),
            base.get("attack", 8),
            base.get("defense", 2),
            floor=floor,
            difficulty=difficulty,
        )
        base["health"] = result.health
        base["attack"] = result.attack
        base["defense"] = result.defense
        scaled["base_stats"] = base
        return scaled

    # ── 商店价格缩放 ──────────────────────────────────────────────────────

    def shop_price_mult(self, floor: int = 1, difficulty: int = 1) -> float:
        return (
            (1.0 + max(0, floor - 1) * SHOP_PRICE_FLOOR_MULT)
            * (1.0 + max(0, difficulty) * SHOP_PRICE_DIFFICULTY_MULT)
        )

    def scale_price(self, base_price: int,
                    floor: int = 1, difficulty: int = 1) -> int:
        return max(1, int(base_price * self.shop_price_mult(floor, difficulty)))

    # ── 房间分配比例 ──────────────────────────────────────────────────────

    def elite_ratio(self, floor: int = 1) -> float:
        """精英房间应占比例（用于地图生成时的额外约束）"""
        ratio = ELITE_BASE_RATIO + max(0, floor - 1) * ELITE_PER_FLOOR
        return min(ratio, ELITE_MAX_RATIO)

    # ── 遗物掉落 ──────────────────────────────────────────────────────────

    def relic_drop_chance(self, floor: int = 1) -> float:
        """普通战斗的遗物掉落概率"""
        chance = RELIC_BASE_DROP_CHANCE + max(0, floor - 1) * RELIC_DROP_FLOOR_BONUS
        return min(chance, RELIC_DROP_MAX)

    # ── 玩家挑战奖励 ──────────────────────────────────────────────────────

    def gold_reward_mult(self, floor: int = 1, difficulty: int = 1) -> float:
        """
        挑战难度更高奖励更多金币（鼓励高难度通关）。
        每级难度 +10%。
        """
        return 1.0 + max(0, difficulty - 1) * 0.10
