"""
卡牌数据模型 - 对应开发计划 6-1
定义 Card 类，包含名称、费用、类型、效果描述、效果执行方法接口。

对应文档 §5.3 卡牌/技能系统
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.utils.enums import CardType, Rarity


@dataclass
class CardEffect:
    """
    卡牌效果数据。
    存储从 YAML 配置中解析出的效果参数。
    """
    damage: int = 0
    block: int = 0
    heal: int = 0
    draw: int = 0                     # 抽卡数量
    energy_gain: int = 0              # 获得能量
    aoe: bool = False                 # 是否范围伤害
    element: str = ""                 # 伤害属性 (fire/ice/lightning/dark/void)
    apply_buff: str = ""              # 施加buff类型
    buff_stacks: int = 1             # buff层数
    buff_target: str = "enemy"       # buff目标 (enemy/self)
    summon: str = ""                  # 召唤物ID
    summon_count: int = 0            # 召唤数量
    max_health_bonus: int = 0        # 永久增加最大生命
    attack_bonus: int = 0            # 永久增加攻击力
    exhaust: bool = False            # 使用后消耗(进入消耗堆)
    extra: Dict[str, Any] = field(default_factory=dict)  # 其他扩展字段

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CardEffect":
        """从配置字典创建 CardEffect"""
        if not data:
            return cls()
        known_fields = {
            "damage", "block", "heal", "draw", "energy_gain",
            "aoe", "element", "apply_buff", "buff_stacks", "buff_target",
            "summon", "summon_count", "max_health_bonus", "attack_bonus", "exhaust",
        }
        kwargs = {}
        extra = {}
        for key, value in data.items():
            if key in known_fields:
                kwargs[key] = value
            else:
                extra[key] = value
        kwargs["extra"] = extra
        return cls(**kwargs)


@dataclass
class Card:
    """
    卡牌数据模型。

    属性:
        card_id:     唯一标识符 (如 'slash', 'fireball')
        name:        显示名称
        card_type:   卡牌类型 (attack/skill/ability/cursed)
        cost:        能量费用
        description: 效果描述文本
        effect:      效果数据
        rarity:      稀有度
        upgraded:    是否已升级
        upgraded_name:        升级后名称
        upgraded_description: 升级后描述
        upgraded_effect:      升级后效果
        character_class:      所属角色职业 (空字符串表示通用)
    """
    card_id: str = ""
    name: str = ""
    card_type: CardType = CardType.ATTACK
    cost: int = 1
    description: str = ""
    effect: CardEffect = field(default_factory=CardEffect)
    rarity: Rarity = Rarity.COMMON
    upgraded: bool = False
    upgraded_name: str = ""
    upgraded_description: str = ""
    upgraded_effect: CardEffect = field(default_factory=CardEffect)
    character_class: str = ""

    # ─── 属性访问 ─────────────────────────────────────────────────────────

    @property
    def display_name(self) -> str:
        """显示名称，升级后带 '+' 标记"""
        if self.upgraded:
            return self.upgraded_name if self.upgraded_name else f"{self.name}+"
        return self.name

    @property
    def display_description(self) -> str:
        """显示描述，升级后使用升级描述"""
        if self.upgraded and self.upgraded_description:
            return self.upgraded_description
        return self.description

    @property
    def active_effect(self) -> CardEffect:
        """当前生效的效果（升级前/后）"""
        if self.upgraded and self.upgraded_effect.damage > 0 or (
            self.upgraded and any([
                self.upgraded_effect.block,
                self.upgraded_effect.heal,
                self.upgraded_effect.draw,
                self.upgraded_effect.apply_buff,
                self.upgraded_effect.summon,
                self.upgraded_effect.max_health_bonus,
                self.upgraded_effect.attack_bonus,
            ])
        ):
            return self.upgraded_effect
        return self.effect

    # ─── 升级 ─────────────────────────────────────────────────────────────

    def can_upgrade(self) -> bool:
        """是否可以升级"""
        return not self.upgraded

    def upgrade(self) -> bool:
        """
        执行升级，不可重复升级。
        返回 True 表示升级成功。
        """
        if self.upgraded:
            return False
        self.upgraded = True
        return True

    # ─── 效果执行接口 ─────────────────────────────────────────────────────

    def get_damage(self) -> int:
        """获取卡牌伤害值"""
        return self.active_effect.damage

    def get_block(self) -> int:
        """获取卡牌格挡值"""
        return self.active_effect.block

    def is_aoe(self) -> bool:
        """是否为范围伤害"""
        return self.active_effect.aoe

    def is_exhaust(self) -> bool:
        """使用后是否消耗"""
        return self.active_effect.exhaust or self.card_type == CardType.ABILITY

    # ─── 工厂方法 ─────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "Card":
        """
        从配置字典创建 Card 实例。
        config 结构对应 config/cards/*.yaml 中的单条卡牌配置。
        """
        # 解析类型
        type_str = config.get("type", "attack")
        try:
            card_type = CardType(type_str)
        except ValueError:
            card_type = CardType.ATTACK

        # 解析稀有度
        rarity_str = config.get("rarity", "common")
        try:
            rarity = Rarity(rarity_str)
        except ValueError:
            rarity = Rarity.COMMON

        # 解析效果
        effect_data = config.get("effect", {})
        effect = CardEffect.from_dict(effect_data)

        # 解析升级效果
        upgraded_effect_data = config.get("upgraded_effect", {})
        upgraded_effect = CardEffect.from_dict(upgraded_effect_data)

        return cls(
            card_id=config.get("id", ""),
            name=config.get("name", "未命名卡牌"),
            card_type=card_type,
            cost=config.get("cost", 1),
            description=config.get("description", ""),
            effect=effect,
            rarity=rarity,
            upgraded=False,
            upgraded_name=config.get("upgraded_name", ""),
            upgraded_description=config.get("upgraded_description", ""),
            upgraded_effect=upgraded_effect,
            character_class=config.get("character_class", ""),
        )

    def copy(self) -> "Card":
        """创建卡牌的深拷贝"""
        import copy
        return copy.deepcopy(self)

    def __repr__(self) -> str:
        up = "+" if self.upgraded else ""
        return f"Card({self.card_id}{up}, cost={self.cost}, type={self.card_type.value})"
