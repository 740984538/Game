"""
遗物数据类与管理器 - 对应开发计划 8-1 / 8-4，文档 §5.2 / §10.4.3

本模块包含：
  - RelicEffect    单条遗物效果数据类
  - Relic          遗物实体（含 effect 派发）
  - RelicManager   当局持有遗物的容器，桥接事件总线触发效果

效果框架设计 (8-4)：
  每个遗物的 effects 列表中，每条 effect 含：
    trigger:     字符串事件名，与 EventManager 发布的事件名一致
    effect_type: 字符串效果类型（见 _EFFECT_HANDLERS 注册表）
    value:       浮点数值
    condition:   可选的字符串表达式（保留扩展点，目前仅做记录）

  RelicManager 在初始化时收集所有 trigger，并在事件总线上注册回调，
  当对应事件被发布时遍历 active_relics 并按 effect_type 派发到具体处理函数，
  通过 ``context`` 字典在调用方与遗物间传递可被修改的数值。

调用方使用模式：
  ctx = {"damage": 10, "attacker": eid, "target": tid}
  ctx = relic_manager.trigger("on_deal_damage", ctx)
  final_damage = ctx["damage"]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from src.core.event_manager import event_manager
from src.utils.enums import Rarity, RelicTrigger

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 8-1: 数据模型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RelicEffect:
    """
    单条遗物效果。

    trigger 与 effect_type 均使用字符串常量便于 YAML 直接映射；
    可通过 :pyattr:`trigger_enum` 获取对应的 RelicTrigger 枚举值（若识别）。
    """
    trigger: str                        # 触发事件名，如 "on_hit"、"on_deal_damage"
    effect_type: str                    # 效果类型 key（见 _EFFECT_HANDLERS）
    value: float = 0.0                  # 效果数值
    condition: Optional[str] = None     # 触发条件表达式（可选，预留扩展）

    @property
    def trigger_enum(self) -> Optional[RelicTrigger]:
        """尝试将 trigger 字符串映射到 RelicTrigger 枚举，未知返回 None。"""
        try:
            return RelicTrigger(self.trigger)
        except ValueError:
            return None


class Relic:
    """
    遗物实体（对应文档 §5.2）。

    遗物为不可变的静态数据 + 一组 effects。
    具体效果在 :py:meth:`apply` 时根据事件名派发到处理器。
    """

    __slots__ = ("id", "name", "rarity", "rarity_enum", "description", "effects", "_triggers")

    def __init__(self, relic_id: str, config: dict) -> None:
        self.id: str = relic_id
        self.name: str = config["name"]
        rarity_str: str = config.get("rarity", "common")
        self.rarity: str = rarity_str
        try:
            self.rarity_enum: Rarity = Rarity(rarity_str)
        except ValueError:
            self.rarity_enum = Rarity.COMMON
        self.description: str = config.get("description", "")
        self.effects: List[RelicEffect] = [
            RelicEffect(
                trigger=e["trigger"],
                effect_type=e["effect_type"],
                value=float(e.get("value", 0)),
                condition=e.get("condition"),
            )
            for e in config.get("effects", [])
        ]
        # 缓存所有触发事件名，便于 RelicManager 注册订阅
        self._triggers: set = {e.trigger for e in self.effects}

    # ── 公共接口 ──────────────────────────────────────────────────────────

    def applies_to(self, event: str) -> bool:
        """是否有任意一条 effect 监听该事件"""
        return event in self._triggers

    def apply(self, event: str, context: dict) -> dict:
        """
        根据触发事件应用该遗物的所有匹配效果。

        :param event:   触发事件名
        :param context: 可变上下文字典；处理器可在此读取/写入数值
        :return:        修改后的 context（同对象，便于链式调用）
        """
        for effect in self.effects:
            if effect.trigger != event:
                continue
            self._apply_effect(effect, context)
        return context

    # ── 内部派发 ──────────────────────────────────────────────────────────

    def _apply_effect(self, effect: RelicEffect, context: dict) -> None:
        """将单条 effect 派发到 _EFFECT_HANDLERS 中对应的处理函数。"""
        handler = _EFFECT_HANDLERS.get(effect.effect_type)
        if handler is None:
            # 未识别的 effect_type 仅记日志，方便策划查错
            logger.debug("未注册的遗物效果类型: %s (relic=%s)", effect.effect_type, self.id)
            return
        try:
            handler(effect, context)
        except Exception as exc:  # 防止单个遗物异常影响整个流程
            logger.exception("遗物 %s 效果 %s 执行失败: %s", self.id, effect.effect_type, exc)

    # ── 调试 ──────────────────────────────────────────────────────────────

    def __repr__(self) -> str:  # pragma: no cover
        return f"Relic(id={self.id!r}, name={self.name!r}, rarity={self.rarity!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Relic) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


# ═══════════════════════════════════════════════════════════════════════════════
# 8-4: 效果处理器注册表
# 每个处理函数接收 (effect, context) 并就地修改 context。
# 上下文常用键约定：
#   damage, base_damage  : 当前/基础伤害
#   block, attack, defense, max_health
#   gold                 : 金币变动
#   target, attacker     : 实体 ID
#   discount             : 商店折扣（0~1）
# ═══════════════════════════════════════════════════════════════════════════════

EffectHandler = Callable[[RelicEffect, dict], None]


def _h_max_health_bonus(effect: RelicEffect, ctx: dict) -> None:
    """on_pickup: 增加最大生命值"""
    ctx["max_health_bonus"] = ctx.get("max_health_bonus", 0) + int(effect.value)


def _h_attack_bonus(effect: RelicEffect, ctx: dict) -> None:
    """on_pickup / on_attack: 攻击力固定值加成"""
    ctx["attack_bonus"] = ctx.get("attack_bonus", 0) + int(effect.value)


def _h_attack_percent_bonus(effect: RelicEffect, ctx: dict) -> None:
    """on_pickup: 百分比攻击加成（叠加）"""
    ctx["attack_percent_bonus"] = ctx.get("attack_percent_bonus", 0.0) + float(effect.value)


def _h_attack_multiplier(effect: RelicEffect, ctx: dict) -> None:
    """on_pickup: 攻击力倍率（与百分比加成一同生效）"""
    cur = ctx.get("attack_multiplier", 1.0)
    ctx["attack_multiplier"] = cur * float(effect.value)


def _h_set_defense(effect: RelicEffect, ctx: dict) -> None:
    """on_pickup: 直接设置防御值（破釜沉舟类）"""
    ctx["defense_set"] = int(effect.value)


def _h_conditional_attack_bonus(effect: RelicEffect, ctx: dict) -> None:
    """on_attack: 满足 condition 时百分比加伤"""
    if _check_condition(effect.condition, ctx):
        ctx["damage_multiplier"] = ctx.get("damage_multiplier", 1.0) * (1.0 + float(effect.value))


def _h_stacking_attack_bonus(effect: RelicEffect, ctx: dict) -> None:
    """on_kill: 累计永久攻击加成（写入 context 由战斗系统读取）"""
    ctx["permanent_attack_gain"] = ctx.get("permanent_attack_gain", 0) + int(effect.value)


def _h_damage_reduction(effect: RelicEffect, ctx: dict) -> None:
    """on_block: 格挡时再减伤"""
    cur = ctx.get("damage_taken_multiplier", 1.0)
    ctx["damage_taken_multiplier"] = cur * (1.0 - float(effect.value))


def _h_damage_bonus(effect: RelicEffect, ctx: dict) -> None:
    """on_deal_damage: 满足条件时增伤"""
    if _check_condition(effect.condition, ctx):
        cur = ctx.get("damage_multiplier", 1.0)
        ctx["damage_multiplier"] = cur * (1.0 + float(effect.value))


def _h_lifesteal(effect: RelicEffect, ctx: dict) -> None:
    """on_deal_damage / on_crit: 吸取造成伤害的百分比"""
    damage = ctx.get("damage", 0)
    heal = int(damage * float(effect.value))
    if heal > 0:
        ctx["heal_amount"] = ctx.get("heal_amount", 0) + heal


def _h_reflect_damage(effect: RelicEffect, ctx: dict) -> None:
    """on_damaged: 反弹百分比伤害"""
    damage = ctx.get("damage", 0)
    reflect = int(damage * float(effect.value))
    if reflect > 0:
        ctx["reflect_damage"] = ctx.get("reflect_damage", 0) + reflect


def _h_max_health_reduction(effect: RelicEffect, ctx: dict) -> None:
    """on_damaged: 受击后扣除最大生命值上限（诅咒类）"""
    ctx["max_health_reduction"] = ctx.get("max_health_reduction", 0) + int(effect.value)


def _h_gain_gold(effect: RelicEffect, ctx: dict) -> None:
    """on_floor_start: 获得金币"""
    ctx["gold_gain"] = ctx.get("gold_gain", 0) + int(effect.value)


def _h_shop_discount(effect: RelicEffect, ctx: dict) -> None:
    """on_shop_open: 商店折扣（取最大折扣）"""
    cur = ctx.get("shop_discount", 0.0)
    ctx["shop_discount"] = max(cur, float(effect.value))


def _h_reveal_map(effect: RelicEffect, ctx: dict) -> None:
    """on_floor_start: 揭示地图（标记位）"""
    ctx["reveal_map"] = True


def _h_extra_choice(effect: RelicEffect, ctx: dict) -> None:
    """on_relic_choice: 遗物选择时额外多一个候选"""
    ctx["extra_relic_choices"] = ctx.get("extra_relic_choices", 0) + int(effect.value)


def _h_execute(effect: RelicEffect, ctx: dict) -> None:
    """on_crit: 当目标 HP 比例 < value 时秒杀"""
    target_hp_pct = ctx.get("target_hp_pct", 1.0)
    if target_hp_pct <= float(effect.value):
        ctx["execute"] = True


def _h_revive_full_hp(effect: RelicEffect, ctx: dict) -> None:
    """on_death: 满血复活（一局一次，由调用方校验 condition）"""
    if _check_condition(effect.condition, ctx):
        ctx["revive"] = True


def _h_aoe_damage(effect: RelicEffect, ctx: dict) -> None:
    """on_combo_threshold: 触发全屏 AOE（伤害值由调用方读取）"""
    if _check_condition(effect.condition, ctx):
        ctx["aoe_damage"] = ctx.get("aoe_damage", 0) + int(effect.value)


def _h_reset_random_cooldown(effect: RelicEffect, ctx: dict) -> None:
    """on_floor_end: 标记重置一个随机冷却（由调用方处理具体技能）"""
    ctx["reset_cooldown_count"] = ctx.get("reset_cooldown_count", 0) + int(effect.value)


_EFFECT_HANDLERS: Dict[str, EffectHandler] = {
    "max_health_bonus":          _h_max_health_bonus,
    "attack_bonus":              _h_attack_bonus,
    "attack_percent_bonus":      _h_attack_percent_bonus,
    "attack_multiplier":         _h_attack_multiplier,
    "set_defense":               _h_set_defense,
    "conditional_attack_bonus":  _h_conditional_attack_bonus,
    "stacking_attack_bonus":     _h_stacking_attack_bonus,
    "damage_reduction":          _h_damage_reduction,
    "damage_bonus":              _h_damage_bonus,
    "lifesteal":                 _h_lifesteal,
    "reflect_damage":            _h_reflect_damage,
    "max_health_reduction":      _h_max_health_reduction,
    "gain_gold":                 _h_gain_gold,
    "shop_discount":             _h_shop_discount,
    "reveal_map":                _h_reveal_map,
    "extra_choice":              _h_extra_choice,
    "execute":                   _h_execute,
    "revive_full_hp":            _h_revive_full_hp,
    "aoe_damage":                _h_aoe_damage,
    "reset_random_cooldown":     _h_reset_random_cooldown,
}


def _check_condition(expr: Optional[str], ctx: dict) -> bool:
    """
    校验 effect 的 condition。

    支持的简单表达式（更复杂的语法可后续扩展为 ast.parse）：
      - None / "" / "always"          → True
      - "hp_percent < 0.3"            → ctx["hp_percent"] < 0.3
      - "combo % 10 == 0"             → ctx["combo"] % 10 == 0
      - "element == fire"             → ctx.get("element") == "fire"
      - "not_used_this_run"           → not ctx.get("used_this_run", False)
    未知表达式默认返回 True，避免阻塞游戏，仅记日志。
    """
    if not expr or expr.strip() in ("always", "true"):
        return True
    expr = expr.strip()

    try:
        # 形如 "hp_percent < 0.3" 等比较
        for op in ("<=", ">=", "==", "!=", "<", ">"):
            if op in expr:
                left, right = (s.strip() for s in expr.split(op, 1))
                lv = ctx.get(left, 0)
                # 右侧可能是数字、字符串字面量或 ctx 变量
                rv = _parse_value(right, ctx)
                return _compare(lv, rv, op)

        # 形如 "combo % 10 == 0"（无空格变体已在上面处理）
        if "%" in expr and "==" in expr:
            return False  # 简化：上面处理了带空格的

        # 命名条件
        if expr == "not_used_this_run":
            return not ctx.get("used_this_run", False)

        return True
    except Exception:
        logger.debug("无法解析遗物 condition: %r", expr)
        return True


def _parse_value(token: str, ctx: dict):
    token = token.strip()
    # 数字
    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        pass
    # 字符串字面量
    if token.startswith(('"', "'")) and token.endswith(('"', "'")):
        return token[1:-1]
    # ctx 变量
    if token in ctx:
        return ctx[token]
    # 当作字符串
    return token


def _compare(lv, rv, op: str) -> bool:
    if op == "<":  return lv < rv
    if op == ">":  return lv > rv
    if op == "<=": return lv <= rv
    if op == ">=": return lv >= rv
    if op == "==": return lv == rv
    if op == "!=": return lv != rv
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# 8-1 / 8-4: 遗物管理器
# ═══════════════════════════════════════════════════════════════════════════════

class RelicManager:
    """
    管理玩家当局持有的遗物列表，并通过事件总线触发效果。

    使用方式：
        relic_pool = ConfigLoader().load_relics()
        mgr = RelicManager(relic_pool)
        mgr.add_relic("iron_will")              # 拾取（自动触发 on_pickup）
        ...
        ctx = {"damage": 10, "hp_percent": 0.2}
        ctx = mgr.trigger("on_attack", ctx)     # 战斗系统手动触发
        # 或自动通过事件总线触发（mgr 已订阅所有遗物的 trigger 事件）
    """

    def __init__(self, relic_pool: Dict[str, dict]) -> None:
        self.active_relics: List[Relic] = []
        self._pool: Dict[str, dict] = relic_pool
        self._subscribed_events: set = set()
        self._latest_context: dict = {}  # 最近一次自动触发的 context（供调用方读取副作用）

    # ── 拾取 / 移除 ───────────────────────────────────────────────────────

    def add_relic(self, relic_id: str) -> Optional[Relic]:
        """
        拾取遗物，加入当局列表。

        若遗物 ID 不在 pool 或重复拾取，返回 None。
        """
        if relic_id not in self._pool:
            logger.warning("尝试拾取未知遗物: %s", relic_id)
            return None
        if any(r.id == relic_id for r in self.active_relics):
            logger.info("遗物 %s 已持有，跳过", relic_id)
            return None

        relic = Relic(relic_id, self._pool[relic_id])
        self.active_relics.append(relic)

        # 8-4: 自动为新遗物的 trigger 事件订阅事件总线
        for trigger in relic._triggers:
            self._ensure_subscribed(trigger)

        # 立即触发 on_pickup
        if relic.applies_to(RelicTrigger.ON_PICKUP.value):
            pickup_ctx: dict = {"relic": relic}
            relic.apply(RelicTrigger.ON_PICKUP.value, pickup_ctx)
            self._latest_context = pickup_ctx

        event_manager.publish("on_relic_picked", relic=relic)
        logger.info("拾取遗物: %s [%s]", relic.name, relic.rarity)
        return relic

    def remove_relic(self, relic_id: str) -> bool:
        """移除一个遗物（事件/商店等可能用到）"""
        for i, relic in enumerate(self.active_relics):
            if relic.id == relic_id:
                del self.active_relics[i]
                logger.info("移除遗物: %s", relic_id)
                return True
        return False

    def has_relic(self, relic_id: str) -> bool:
        return any(r.id == relic_id for r in self.active_relics)

    def clear(self) -> None:
        """清空当局遗物（不移除事件订阅，订阅在重置时统一清理）"""
        self.active_relics.clear()
        self._latest_context = {}

    # ── 事件触发 ──────────────────────────────────────────────────────────

    def trigger(self, event: str, context: Optional[dict] = None) -> dict:
        """
        主动触发遗物效果（通常由战斗系统在伤害结算等关键节点调用）。

        :return: 修改后的 context 字典（永远非 None）
        """
        ctx = dict(context) if context else {}
        for relic in self.active_relics:
            if relic.applies_to(event):
                relic.apply(event, ctx)
        return ctx

    @property
    def latest_context(self) -> dict:
        """最近一次自动事件触发后的 context（用于读取诸如 max_health_bonus 的副作用）"""
        return dict(self._latest_context)

    # ── 内部：事件订阅 ────────────────────────────────────────────────────

    def _ensure_subscribed(self, event: str) -> None:
        """为指定事件名注册事件总线回调（同一事件只订阅一次）"""
        if event in self._subscribed_events or event == RelicTrigger.ON_PICKUP.value:
            return
        # ON_PICKUP 由 add_relic 直接处理，无需通过事件总线
        event_manager.subscribe(event, self._make_event_callback(event))
        self._subscribed_events.add(event)

    def _make_event_callback(self, event: str):
        """生成绑定到具体事件的回调闭包"""
        def _callback(**kwargs):
            ctx = dict(kwargs)
            for relic in self.active_relics:
                if relic.applies_to(event):
                    relic.apply(event, ctx)
            self._latest_context = ctx
        return _callback

    def unsubscribe_all(self) -> None:
        """从事件总线移除所有订阅（换局/退出战斗时调用）"""
        # EventManager 没有按订阅者批量移除接口，这里通过 clear 重置 latest_context；
        # 实际清理由调用方在 event_manager.clear() 时统一完成。
        self._subscribed_events.clear()
        self._latest_context = {}

    # ── 序列化辅助 ────────────────────────────────────────────────────────

    def get_relic_ids(self) -> List[str]:
        """返回当局所有遗物 ID（供存档使用）"""
        return [r.id for r in self.active_relics]

    def __len__(self) -> int:
        return len(self.active_relics)
