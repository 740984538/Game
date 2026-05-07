"""
敌人数据模型 - 对应开发计划 6-13
定义 EnemyData 类，从 config/enemies/ 解析敌人属性。

提供:
  - EnemyData: 敌人配置数据封装
  - 解析敌人属性（HP、攻击力、意图模式、特殊技能等）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EnemyAction:
    """敌人单个行动定义"""
    action_type: str = "attack"     # attack / defend / buff / debuff / special
    value: int = 0                   # 伤害/格挡数值
    buff_type: str = ""             # 施加的buff
    buff_stacks: int = 1            # buff层数
    weight: float = 1.0             # 行动权重(用于AI随机选择)
    description: str = ""           # 行动描述


@dataclass
class EnemySkill:
    """敌人特殊技能（精英/BOSS用）"""
    skill_id: str = ""
    description: str = ""
    cooldown: float = 3.0
    damage: int = 0
    effect: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnemyDropTable:
    """敌人掉落表"""
    gold_min: int = 0
    gold_max: int = 0
    relic_drop_chance: float = 0.0
    essence: int = 0
    relic_choices: int = 0


@dataclass
class EnemyData:
    """
    敌人配置数据封装。
    对应 config/enemies/*.yaml 中的敌人定义。

    属性:
        enemy_id:     唯一标识符
        name:         显示名称
        enemy_type:   类型 (common/elite/boss)
        health:       基础生命值
        attack:       基础攻击力
        defense:      基础防御力
        speed:        行动速度
        crit_rate:    暴击率
        dodge_rate:   闪避率
        ai_pattern:   AI行为模式
        actions:      行动列表
        special_skills: 特殊技能（精英/BOSS）
        drop_table:   掉落表
        floor:        出现楼层（BOSS用）
    """
    enemy_id: str = ""
    name: str = ""
    enemy_type: str = "common"
    health: int = 30
    attack: int = 8
    defense: int = 2
    speed: float = 4.0
    crit_rate: float = 0.0
    dodge_rate: float = 0.0
    ai_pattern: str = "melee_aggressive"
    actions: List[EnemyAction] = field(default_factory=list)
    special_skills: List[EnemySkill] = field(default_factory=list)
    drop_table: EnemyDropTable = field(default_factory=EnemyDropTable)
    floor: int = 0  # BOSS 出现的楼层

    # ─── 工厂方法 ─────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "EnemyData":
        """从 YAML 配置字典创建 EnemyData"""
        stats = config.get("base_stats", {})

        # 解析行动模式
        actions = []
        for action_cfg in config.get("actions", []):
            actions.append(EnemyAction(
                action_type=action_cfg.get("type", "attack"),
                value=action_cfg.get("value", 0),
                buff_type=action_cfg.get("buff_type", ""),
                buff_stacks=action_cfg.get("buff_stacks", 1),
                weight=action_cfg.get("weight", 1.0),
                description=action_cfg.get("description", ""),
            ))

        # 如果没有定义 actions，根据 base_stats 生成默认行动
        if not actions:
            attack_val = stats.get("attack", 8)
            actions = [
                EnemyAction(action_type="attack", value=attack_val, weight=2.0,
                            description=f"攻击造成{attack_val}点伤害"),
                EnemyAction(action_type="defend", value=5, weight=1.0,
                            description="获得5点格挡"),
            ]

        # 解析特殊技能
        skills = []
        for skill_cfg in config.get("special_skills", []):
            skills.append(EnemySkill(
                skill_id=skill_cfg.get("id", ""),
                description=skill_cfg.get("description", ""),
                cooldown=float(skill_cfg.get("cooldown", 3.0)),
                damage=skill_cfg.get("damage", 0),
                effect=skill_cfg.get("effect", {}),
            ))

        # 解析掉落表
        drop_cfg = config.get("drop_table", {})
        drop_table = EnemyDropTable(
            gold_min=drop_cfg.get("gold_min", 0),
            gold_max=drop_cfg.get("gold_max", 0),
            relic_drop_chance=drop_cfg.get("relic_drop_chance", 0.0),
            essence=drop_cfg.get("essence", 0),
            relic_choices=drop_cfg.get("relic_choices", 0),
        )

        return cls(
            enemy_id=config.get("id", ""),
            name=config.get("name", "未知敌人"),
            enemy_type=config.get("type", "common"),
            health=stats.get("health", 30),
            attack=stats.get("attack", 8),
            defense=stats.get("defense", 2),
            speed=float(stats.get("speed", 4)),
            crit_rate=float(stats.get("crit_rate", 0.0)),
            dodge_rate=float(stats.get("dodge_rate", 0.0)),
            ai_pattern=config.get("ai_pattern", "melee_aggressive"),
            actions=actions,
            special_skills=skills,
            drop_table=drop_table,
            floor=config.get("floor", 0),
        )

    def to_entity_config(self) -> Dict[str, Any]:
        """
        转换为 EntityFactory.create_enemy 所需的配置字典格式。
        """
        config = {
            "id": self.enemy_id,
            "name": self.name,
            "type": self.enemy_type,
            "base_stats": {
                "health": self.health,
                "attack": self.attack,
                "defense": self.defense,
                "speed": self.speed,
                "crit_rate": self.crit_rate,
                "dodge_rate": self.dodge_rate,
            },
            "ai_pattern": self.ai_pattern,
            "special_skills": [
                {
                    "id": sk.skill_id,
                    "description": sk.description,
                    "cooldown": sk.cooldown,
                }
                for sk in self.special_skills
            ],
            "drop_table": {
                "gold_min": self.drop_table.gold_min,
                "gold_max": self.drop_table.gold_max,
                "relic_drop_chance": self.drop_table.relic_drop_chance,
                "essence": self.drop_table.essence,
                "relic_choices": self.drop_table.relic_choices,
            },
        }
        return config

    def scale_for_floor(self, floor_number: int) -> "EnemyData":
        """
        根据楼层缩放敌人属性，返回新的 EnemyData。
        每层 HP +10%, 攻击 +8%, 防御 +5%
        """
        import copy
        scaled = copy.deepcopy(self)
        scale_factor = 1.0 + (floor_number - 1) * 0.1
        atk_factor = 1.0 + (floor_number - 1) * 0.08
        def_factor = 1.0 + (floor_number - 1) * 0.05

        scaled.health = int(self.health * scale_factor)
        scaled.attack = int(self.attack * atk_factor)
        scaled.defense = int(self.defense * def_factor)

        # 更新 actions 中的数值
        for action in scaled.actions:
            if action.action_type == "attack":
                action.value = int(action.value * atk_factor)
            elif action.action_type == "defend":
                action.value = int(action.value * def_factor)

        return scaled

    def __repr__(self) -> str:
        return (f"EnemyData({self.enemy_id}, type={self.enemy_type}, "
                f"hp={self.health}, atk={self.attack})")
