"""
全局枚举定义
对应文档 §10.3.3 状态机、§4.1.2 房间类型、§5.2.2 遗物稀有度
"""
from enum import Enum, auto


class GameState(Enum):
    """游戏状态枚举，对应状态机的每个节点"""
    MAIN_MENU = auto()
    CHARACTER_SELECT = auto()
    MAP_NAVIGATION = auto()
    COMBAT = auto()
    SHOP = auto()
    EVENT = auto()
    REST = auto()
    RELIC_SELECT = auto()
    PAUSE = auto()
    GAME_OVER = auto()
    VICTORY = auto()


class RoomType(Enum):
    """房间类型枚举"""
    COMBAT = "combat"
    ELITE = "elite"
    BOSS = "boss"
    SHOP = "shop"
    EVENT = "event"
    REST = "rest"
    HIDDEN = "hidden"


class Rarity(Enum):
    """遗物/卡牌稀有度"""
    COMMON = "common"      # 白色，60%
    RARE = "rare"          # 蓝色，30%
    EPIC = "epic"          # 紫色，9%
    LEGENDARY = "legendary"  # 金色，1%


class CharacterRole(Enum):
    """角色职业"""
    WARRIOR = "warrior"
    ASSASSIN = "assassin"
    MAGE = "mage"
    RANGER = "ranger"
    SUMMONER = "summoner"


class CardType(Enum):
    """卡牌类型"""
    ATTACK = "attack"
    SKILL = "skill"
    ABILITY = "ability"
    CURSED = "cursed"


class DamageType(Enum):
    """伤害类型"""
    PHYSICAL = "physical"
    FIRE = "fire"
    ICE = "ice"
    LIGHTNING = "lightning"
    DARK = "dark"
    VOID = "void"


class BuffType(Enum):
    """Buff/Debuff类型"""
    BURNING = "burning"
    POISONED = "poisoned"
    FROZEN = "frozen"
    STUNNED = "stunned"
    STEALTH = "stealth"
    BLOCKING = "blocking"
    BERSERKING = "berserking"
