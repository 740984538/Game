"""
角色数据模型与属性计算 - 对应开发计划 §3-5（角色数据读取）
提供：
  - CharacterData  角色静态配置对象（从 YAML 构建）
  - calculate_final_stats  运行时最终属性计算（含遗物加成）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.utils.constants import MAX_CRIT_RATE, MAX_DODGE_RATE, MAX_COOLDOWN_REDUCTION
from src.utils.helpers import clamp


# ── 角色数据类 ───────────────────────────────────────────────────────────────

@dataclass
class BaseStats:
    """角色基础属性（直接来自 YAML base_stats 节）"""
    health: int = 80
    attack: int = 10
    defense: int = 5
    speed: int = 5
    crit_rate: float = 0.05
    dodge_rate: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "BaseStats":
        return cls(
            health=d.get("health", 80),
            attack=d.get("attack", 10),
            defense=d.get("defense", 5),
            speed=d.get("speed", 5),
            crit_rate=d.get("crit_rate", 0.05),
            dodge_rate=d.get("dodge_rate", 0.0),
        )

    def to_dict(self) -> dict:
        return {
            "health": self.health,
            "attack": self.attack,
            "defense": self.defense,
            "speed": self.speed,
            "crit_rate": self.crit_rate,
            "dodge_rate": self.dodge_rate,
        }


@dataclass
class CharacterData:
    """
    角色静态配置，对应 config/characters/<id>.yaml 中 character 节。

    使用 :meth:`from_dict` 从 YAML 数据构建实例。
    """
    id: str
    name: str
    description: str
    role: str
    base_stats: BaseStats
    starting_gold: int = 100
    starting_relic: Optional[str] = None
    special_mechanic: str = ""
    unlock_condition: str = "default"
    # 起始卡组（如 YAML 中有 starting_deck 字段）
    starting_deck: List[str] = field(default_factory=list)

    # ── 工厂方法 ─────────────────────────────────────

    @classmethod
    def from_dict(cls, d: dict) -> "CharacterData":
        """
        从 YAML 解析后的字典构建 CharacterData。

        d 对应 ``yaml.safe_load(file)["character"]`` 的内容。
        """
        stats_raw = d.get("base_stats", {})
        return cls(
            id=d["id"],
            name=d.get("name", d["id"]),
            description=d.get("description", ""),
            role=d.get("role", ""),
            base_stats=BaseStats.from_dict(stats_raw),
            starting_gold=d.get("starting_gold", 100),
            starting_relic=d.get("starting_relic"),
            special_mechanic=d.get("special_mechanic", ""),
            unlock_condition=d.get("unlock_condition", "default"),
            starting_deck=d.get("starting_deck", []),
        )

    # ── 便捷属性 ─────────────────────────────────────

    @property
    def is_default_unlocked(self) -> bool:
        """是否默认解锁（无需消耗灵魂碎片）"""
        return self.unlock_condition == "default"

    @property
    def unlock_cost(self) -> int:
        """
        解锁所需灵魂碎片数量。
        unlock_condition 格式：``"soul_shards:200"``，默认解锁返回 0。
        """
        if self.is_default_unlocked:
            return 0
        if self.unlock_condition.startswith("soul_shards:"):
            try:
                return int(self.unlock_condition.split(":")[1])
            except (IndexError, ValueError):
                return 0
        return 0

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"CharacterData(id={self.id!r}, name={self.name!r}, "
            f"hp={self.base_stats.health}, role={self.role!r})"
        )


# ── 角色注册表 ───────────────────────────────────────────────────────────────

class CharacterRegistry:
    """
    全局角色注册表（单例），统一管理从 YAML 加载的所有 CharacterData。

    典型用法::

        registry = CharacterRegistry.instance()
        registry.load_all()                      # 从 config/characters/ 加载
        knight = registry.get("knight")          # 按 id 获取
        chars = registry.all_characters()        # 获取全部
    """

    _instance: Optional["CharacterRegistry"] = None

    @classmethod
    def instance(cls) -> "CharacterRegistry":
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance._characters = {}   # Dict[str, CharacterData]
            cls._instance._loaded = False
        return cls._instance

    def load_all(self, config_dir: str = "config") -> None:
        """
        从 ``config/characters/`` 目录加载所有 YAML 角色配置。

        重复调用会重新加载（清空旧缓存）。
        """
        from src.data.config_loader import ConfigLoader
        loader = ConfigLoader(config_dir)
        raw_map = loader.load_all_characters()
        self._characters = {
            char_id: CharacterData.from_dict(data)
            for char_id, data in raw_map.items()
        }
        self._loaded = True

    def get(self, char_id: str) -> Optional[CharacterData]:
        """按 id 获取角色数据，不存在返回 None。"""
        return self._characters.get(char_id)

    def all_characters(self) -> List[CharacterData]:
        """返回所有已加载角色的列表，按 id 排序。"""
        return sorted(self._characters.values(), key=lambda c: c.id)

    def unlocked_characters(self, unlocked_ids: List[str]) -> List[CharacterData]:
        """
        返回 unlocked_ids 中的角色（保留顺序），
        未在注册表中找到的 id 会被跳过。
        """
        return [c for cid in unlocked_ids if (c := self._characters.get(cid))]

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def __len__(self) -> int:
        return len(self._characters)


# ── 运行时属性计算 ───────────────────────────────────────────────────────────

def calculate_final_stats(base_stats: dict, relic_bonuses: dict) -> dict:
    """
    将基础属性与遗物加成合并，返回最终属性字典。
    对应文档 §3.1.2 单局数值范围规范（上限约束）。

    base_stats 可以是原始 dict 或 ``BaseStats.to_dict()`` 的结果。
    relic_bonuses 示例::

        {
            "attack_percent": 0.1,   # +10% 攻击
            "attack_flat": 5,        # +5 攻击
            "defense_flat": 3,
            "max_health_flat": 20,
            "crit_rate": 0.05,
            "dodge_rate": 0.02,
        }
    """
    final = dict(base_stats)

    final["attack"] = int(
        final.get("attack", 10) * (1 + relic_bonuses.get("attack_percent", 0))
        + relic_bonuses.get("attack_flat", 0)
    )
    final["defense"] = max(0, final.get("defense", 0) + relic_bonuses.get("defense_flat", 0))
    final["max_health"] = final.get("health", 80) + relic_bonuses.get("max_health_flat", 0)
    final["crit_rate"] = clamp(
        final.get("crit_rate", 0.05) + relic_bonuses.get("crit_rate", 0),
        0.0, MAX_CRIT_RATE,
    )
    final["dodge_rate"] = clamp(
        final.get("dodge_rate", 0.0) + relic_bonuses.get("dodge_rate", 0),
        0.0, MAX_DODGE_RATE,
    )
    return final


def build_initial_run_stats(character: CharacterData, relic_bonuses: Optional[dict] = None) -> dict:
    """
    根据角色配置 + 可选遗物加成，生成本局开始时的完整属性字典。

    返回的字典包含 ``max_health`` / ``health`` / ``attack`` 等运行时常用键。
    """
    bonuses = relic_bonuses or {}
    final = calculate_final_stats(character.base_stats.to_dict(), bonuses)
    # 开局 HP = 最大 HP
    final.setdefault("max_health", character.base_stats.health)
    final["health"] = final["max_health"]
    return final
