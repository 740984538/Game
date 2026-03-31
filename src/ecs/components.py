"""
ECS 组件定义
对应文档 §10.3.1 ECS架构说明
所有组件均为纯数据类（dataclass），不含业务逻辑
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


# ── 基础物理组件 ──────────────────────────────────

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


# ── 战斗属性组件 ──────────────────────────────────

@dataclass
class Health:
    """生命值，对应文档 §3.1.2"""
    current: int = 100
    maximum: int = 100


@dataclass
class Combat:
    """战斗属性，对应文档 §3.1.1"""
    attack: int = 10
    defense: int = 5
    speed: float = 5.0
    crit_rate: float = 0.05
    crit_multiplier: float = 1.5
    dodge_rate: float = 0.0


@dataclass
class BuffList:
    """持有的 Buff/Debuff 列表，对应文档 §5.3 技能系统"""
    buffs: List[dict] = field(default_factory=list)


# ── 资源组件 ──────────────────────────────────────

@dataclass
class Wallet:
    """金币，对应文档 §3.2.1 货币体系"""
    gold: int = 0
    essence: int = 0


# ── 渲染组件 ──────────────────────────────────────

@dataclass
class Renderable:
    """可渲染精灵信息，对应文档 §6.1.1 界面层级"""
    sprite_key: str = ""    # 资源管理器中的图片key
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


# ── 标签组件（零数据，仅用于查询过滤）──────────────

@dataclass
class PlayerTag:
    """标记实体为玩家"""
    pass


@dataclass
class EnemyTag:
    """标记实体为敌人"""
    enemy_id: str = ""
    enemy_type: str = "common"   # common / elite / boss


@dataclass
class SummonTag:
    """标记实体为召唤物"""
    owner_entity: Optional[int] = None


# ── AI 组件 ───────────────────────────────────────

@dataclass
class AIController:
    """敌人AI状态，对应文档 §敌人AI设计"""
    ai_pattern: str = "melee_aggressive"
    state: str = "idle"        # idle / chase / attack / retreat
    target_entity: Optional[int] = None
    attack_cooldown: float = 0.0
    detection_range: float = 200.0
    attack_range: float = 60.0


# ── 技能/卡牌组件 ─────────────────────────────────

@dataclass
class CardHolder:
    """持有的卡牌列表（手牌+牌库）"""
    hand: List[str] = field(default_factory=list)
    deck: List[str] = field(default_factory=list)
    discard: List[str] = field(default_factory=list)
    energy: int = 3
    max_energy: int = 3


@dataclass
class RelicHolder:
    """持有的遗物列表"""
    relic_ids: List[str] = field(default_factory=list)
