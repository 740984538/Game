"""
ECS 组件定义
对应文档 §10.3.1 ECS架构说明
对应开发计划: 5-1 ECS 组件定义

所有组件均为纯数据类（dataclass），不含业务逻辑。
组件可附加到 esper 实体上，由 System/Processor 统一处理。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# 基础物理组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Position:
    """世界坐标位置"""
    x: float = 0.0
    y: float = 0.0


@dataclass
class Velocity:
    """移动速度向量"""
    vx: float = 0.0
    vy: float = 0.0


@dataclass
class Collider:
    """碰撞体（AABB矩形）"""
    width: float = 32.0
    height: float = 32.0
    offset_x: float = 0.0
    offset_y: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 渲染组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Sprite:
    """
    精灵渲染信息 (对应开发计划 5-1)。
    用于在战斗场景中绘制实体形象。

    属性:
        sprite_key: 资源管理器中的图片 key (空字符串表示使用占位色块)
        width:      精灵绘制宽度 (像素)
        height:     精灵绘制高度 (像素)
        color:      占位矩形颜色 (无图片时使用)
        layer:      渲染层级 (越大越靠前)
        visible:    是否可见
        flip_x:     是否水平翻转
    """
    sprite_key: str = ""
    width: int = 64
    height: int = 80
    color: Tuple[int, int, int] = (100, 100, 120)
    layer: int = 1
    visible: bool = True
    flip_x: bool = False


@dataclass
class Renderable:
    """可渲染精灵信息（向后兼容保留，新代码推荐使用 Sprite）"""
    sprite_key: str = ""
    layer: int = 0
    visible: bool = True
    flip_x: bool = False


@dataclass
class Animation:
    """精灵动画状态"""
    current_anim: str = "idle"
    frame_index: int = 0
    frame_timer: float = 0.0
    frame_duration: float = 0.1


# ═══════════════════════════════════════════════════════════════════════════════
# 战斗属性组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Health:
    """
    生命值组件 (对应开发计划 5-1 / 文档 §3.1.2)。

    属性:
        current: 当前 HP
        maximum: 最大 HP
    """
    current: int = 100
    maximum: int = 100

    @property
    def is_alive(self) -> bool:
        return self.current > 0

    @property
    def ratio(self) -> float:
        """当前生命比例 (0.0 ~ 1.0)"""
        return self.current / max(1, self.maximum)

    def take_damage(self, amount: int) -> int:
        """
        受到伤害，返回实际扣血量。
        HP 不会低于 0。
        """
        actual = min(amount, self.current)
        self.current -= actual
        return actual

    def heal(self, amount: int) -> int:
        """
        恢复生命值，返回实际恢复量。
        HP 不会超过 maximum。
        """
        actual = min(amount, self.maximum - self.current)
        self.current += actual
        return actual


@dataclass
class Stats:
    """
    战斗属性组件 (对应开发计划 5-1 / 文档 §3.1.1)。
    包含攻击力、防御力、速度、暴击、闪避等核心战斗数值。

    属性:
        attack:          基础攻击力
        defense:         基础防御力
        speed:           行动速度
        crit_rate:       暴击率 (0.0 ~ 0.75)
        crit_multiplier: 暴击伤害倍数
        dodge_rate:      闪避率 (0.0 ~ 0.40)
    """
    attack: int = 10
    defense: int = 5
    speed: float = 5.0
    crit_rate: float = 0.05
    crit_multiplier: float = 1.5
    dodge_rate: float = 0.0


@dataclass
class Combat:
    """战斗属性（向后兼容保留，新代码推荐使用 Stats）"""
    attack: int = 10
    defense: int = 5
    speed: float = 5.0
    crit_rate: float = 0.05
    crit_multiplier: float = 1.5
    dodge_rate: float = 0.0


@dataclass
class Block:
    """
    格挡值组件。
    格挡优先抵消伤害，通常每回合开始清零。
    """
    current: int = 0

    def add_block(self, amount: int) -> None:
        """增加格挡值"""
        self.current += amount

    def absorb_damage(self, damage: int) -> int:
        """
        用格挡吸收伤害。
        返回穿透格挡后剩余的伤害值。
        """
        absorbed = min(damage, self.current)
        self.current -= absorbed
        return damage - absorbed

    def reset(self) -> None:
        """回合开始时清零"""
        self.current = 0


@dataclass
class Energy:
    """
    能量组件，用于卡牌战斗中的费用系统。
    """
    current: int = 3
    maximum: int = 3

    def spend(self, cost: int) -> bool:
        """消耗能量，成功返回 True，不足返回 False"""
        if self.current >= cost:
            self.current -= cost
            return True
        return False

    def restore_full(self) -> None:
        """回合开始时恢复满能量"""
        self.current = self.maximum


# ═══════════════════════════════════════════════════════════════════════════════
# Buff 组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BuffInstance:
    """单个 Buff 数据"""
    buff_type: str = ""        # BuffType 枚举值
    stacks: int = 1            # 层数
    duration: int = -1         # 持续回合 (-1 为永久)
    source_entity: int = -1    # 施加者实体 ID


@dataclass
class BuffList:
    """持有的 Buff/Debuff 列表"""
    buffs: List[BuffInstance] = field(default_factory=list)

    def add_buff(self, buff_type: str, stacks: int = 1, duration: int = -1,
                 source: int = -1) -> None:
        """添加或叠加 buff"""
        for buff in self.buffs:
            if buff.buff_type == buff_type:
                buff.stacks += stacks
                if duration > 0:
                    buff.duration = max(buff.duration, duration)
                return
        self.buffs.append(BuffInstance(
            buff_type=buff_type, stacks=stacks,
            duration=duration, source_entity=source
        ))

    def remove_buff(self, buff_type: str) -> None:
        """移除指定类型的 buff"""
        self.buffs = [b for b in self.buffs if b.buff_type != buff_type]

    def get_stacks(self, buff_type: str) -> int:
        """获取指定 buff 的层数，不存在返回 0"""
        for buff in self.buffs:
            if buff.buff_type == buff_type:
                return buff.stacks
        return 0

    def has_buff(self, buff_type: str) -> bool:
        """是否拥有指定 buff"""
        return any(b.buff_type == buff_type for b in self.buffs)


# ═══════════════════════════════════════════════════════════════════════════════
# 资源组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Wallet:
    """金币与精华，对应文档 §3.2.1 货币体系"""
    gold: int = 0
    essence: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# 标签组件（零数据或少数据，用于查询过滤）
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PlayerTag:
    """标记实体为玩家"""
    character_id: str = ""


@dataclass
class EnemyTag:
    """标记实体为敌人"""
    enemy_id: str = ""
    enemy_type: str = "common"   # common / elite / boss
    name: str = ""               # 敌人显示名称


@dataclass
class SummonTag:
    """标记实体为召唤物"""
    owner_entity: Optional[int] = None


# ═══════════════════════════════════════════════════════════════════════════════
# AI 组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AIController:
    """敌人 AI 状态"""
    ai_pattern: str = "melee_aggressive"
    state: str = "idle"
    target_entity: Optional[int] = None
    attack_cooldown: float = 0.0
    detection_range: float = 200.0
    attack_range: float = 60.0


@dataclass
class IntentDisplay:
    """
    敌人行动意图组件。
    在玩家回合显示敌人下回合计划做什么。
    """
    intent_type: str = "attack"    # attack / defend / buff / debuff / unknown
    intent_value: int = 0          # 预计伤害/格挡数值
    description: str = ""          # 显示文本


# ═══════════════════════════════════════════════════════════════════════════════
# BOSS 阶段组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BossPhaseData:
    """单个阶段数据"""
    phase: int = 1
    hp_threshold: float = 1.0
    description: str = ""
    skills: List[dict] = field(default_factory=list)


@dataclass
class BossController:
    """
    BOSS 多阶段控制组件。
    存储所有阶段数据，跟踪当前阶段。
    """
    phases: List[BossPhaseData] = field(default_factory=list)
    current_phase: int = 1
    boss_name: str = ""
    triggered_phases: List[int] = field(default_factory=list)  # 已经触发过的阶段
    just_transitioned: bool = False                              # 上一次 check 是否切换了阶段
    last_transition_phase: int = 0                                # 上一次切换到的阶段编号

    def get_current_phase_data(self) -> Optional[BossPhaseData]:
        for p in self.phases:
            if p.phase == self.current_phase:
                return p
        return None

    def get_phase_data(self, phase: int) -> Optional[BossPhaseData]:
        for p in self.phases:
            if p.phase == phase:
                return p
        return None

    def check_phase_transition(self, hp_ratio: float) -> bool:
        """
        根据 HP 比例检查是否需要切换阶段。
        返回 True 表示发生了阶段变化（同时设置 just_transitioned 标记）。
        每个阶段只会触发一次（通过 triggered_phases 防止反复触发）。
        """
        self.just_transitioned = False
        # phase 越大代表阶段越后期；hp_threshold 越小越后
        for p in sorted(self.phases, key=lambda x: x.hp_threshold):
            if hp_ratio <= p.hp_threshold and p.phase > self.current_phase:
                if p.phase not in self.triggered_phases:
                    self.current_phase = p.phase
                    self.triggered_phases.append(p.phase)
                    self.just_transitioned = True
                    self.last_transition_phase = p.phase
                    return True
        return False

    @property
    def total_phases(self) -> int:
        return len(self.phases)


# ═══════════════════════════════════════════════════════════════════════════════
# 卡牌/技能组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CardHolder:
    """持有的卡牌列表（手牌 + 抽卡堆 + 弃牌堆）"""
    hand: List[str] = field(default_factory=list)
    deck: List[str] = field(default_factory=list)
    discard: List[str] = field(default_factory=list)
    exhaust: List[str] = field(default_factory=list)  # 消耗堆


@dataclass
class SkillSlot:
    """
    敌人特殊技能槽 (精英/BOSS)。
    """
    skill_id: str = ""
    description: str = ""
    cooldown: float = 0.0
    current_cooldown: float = 0.0

    @property
    def is_ready(self) -> bool:
        return self.current_cooldown <= 0.0

    def use(self) -> None:
        self.current_cooldown = self.cooldown

    def tick(self, dt: float) -> None:
        if self.current_cooldown > 0:
            self.current_cooldown = max(0.0, self.current_cooldown - dt)


@dataclass
class SkillSet:
    """持有的技能列表（用于精英/BOSS 敌人）"""
    skills: List[SkillSlot] = field(default_factory=list)

    def get_ready_skills(self) -> List[SkillSlot]:
        return [s for s in self.skills if s.is_ready]


# ═══════════════════════════════════════════════════════════════════════════════
# 遗物组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RelicHolder:
    """持有的遗物列表"""
    relic_ids: List[str] = field(default_factory=list)

    def add_relic(self, relic_id: str) -> None:
        if relic_id and relic_id not in self.relic_ids:
            self.relic_ids.append(relic_id)

    def has_relic(self, relic_id: str) -> bool:
        return relic_id in self.relic_ids


# ═══════════════════════════════════════════════════════════════════════════════
# 掉落组件
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DropTable:
    """敌人死亡后的掉落配置"""
    gold_min: int = 0
    gold_max: int = 0
    relic_drop_chance: float = 0.0
    essence: int = 0
    relic_choices: int = 0  # BOSS 遗物选择数
