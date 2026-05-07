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
    SETTINGS = auto()
    # 阶段 9 新增
    META_UPGRADE = auto()   # 9-4：局外灵魂碎片消费/解锁
    CODEX = auto()          # 9-10：图鉴（已收集遗物 / 已见卡牌）


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
    # 增益
    STRENGTH = "strength"          # 力量: 攻击伤害 +N
    BERSERKING = "berserking"      # 狂暴: 攻击力提升
    BLOCKING = "blocking"          # 格挡
    REGENERATION = "regeneration"  # 再生: 每回合恢复HP
    STEALTH = "stealth"            # 隐身
    # 减益
    WEAKENED = "weakened"           # 虚弱: 攻击伤害 ×0.75
    VULNERABLE = "vulnerable"      # 易伤: 受到伤害 ×1.5
    POISONED = "poisoned"          # 中毒: 每回合受到等于层数的伤害
    BURNING = "burning"            # 燃烧: 每回合受到固定伤害
    FROZEN = "frozen"              # 冰冻
    STUNNED = "stunned"            # 眩晕


class TargetType(Enum):
    """卡牌目标类型"""
    SINGLE_ENEMY = "single_enemy"   # 单个敌人
    ALL_ENEMIES = "all_enemies"     # 所有敌人
    SELF = "self"                   # 自身
    NONE = "none"                   # 无目标


class RelicTrigger(Enum):
    """
    遗物效果触发时机（对应开发计划 8-4）。

    所有事件名与 EventManager.publish 的事件名保持一致，
    遗物效果通过 RelicManager 在对应事件发生时被自动应用。
    """
    # 拾取 / 局开始
    ON_PICKUP = "on_pickup"                  # 拾取遗物时（用于 max_health_bonus 等被动加成）
    ON_BATTLE_START = "on_battle_start"      # 战斗开始
    ON_FLOOR_START = "on_floor_start"        # 进入新楼层

    # 回合
    ON_TURN_START = "on_player_turn_start"   # 玩家回合开始
    ON_TURN_END = "on_player_turn_end"       # 玩家回合结束

    # 战斗内
    ON_ATTACK = "on_attack"                  # 玩家发起攻击时
    ON_DEAL_DAMAGE = "on_deal_damage"        # 造成伤害时
    ON_DAMAGED = "on_damaged"                # 受到伤害时
    ON_BLOCK = "on_block"                    # 格挡触发时
    ON_CRIT = "on_crit"                      # 暴击触发时
    ON_KILL = "on_kill"                      # 击杀敌人时
    ON_DEATH = "on_death"                    # 玩家死亡时

    # 战斗结束 / 经济
    ON_BATTLE_WIN = "on_battle_win"          # 战斗胜利
    ON_FLOOR_END = "on_floor_end"            # 完成当前楼层
    ON_SHOP_OPEN = "on_shop_open"            # 进入商店
    ON_RELIC_CHOICE = "on_relic_choice"      # 即将展示遗物选择时
    ON_COMBO_THRESHOLD = "on_combo_threshold"  # 连击阈值达成（传说遗物使用）
