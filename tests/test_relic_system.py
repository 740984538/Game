"""
遗物系统单元测试 - 对应开发计划 8-1 / 8-4
覆盖：
  - RelicEffect / Relic 数据模型（含 RelicTrigger 枚举映射、Rarity 枚举）
  - RelicManager 拾取、移除、清空
  - 效果派发：max_health_bonus / damage_bonus / lifesteal / reflect_damage / execute / shop_discount
  - condition 表达式解析
  - 通过事件总线自动触发
"""
import pytest
from src.entities.relics.relic_manager import (
    Relic, RelicEffect, RelicManager, _check_condition,
)
from src.utils.enums import Rarity, RelicTrigger
from src.core.event_manager import EventManager, event_manager


MOCK_POOL = {
    "iron_will": {
        "id": "iron_will",
        "name": "钢铁意志",
        "rarity": "common",
        "description": "生命值上限+20",
        "effects": [{"trigger": "on_pickup", "effect_type": "max_health_bonus", "value": 20}],
    },
    "blood_rage": {
        "id": "blood_rage",
        "name": "血怒",
        "rarity": "rare",
        "description": "HP<30% 时攻击力+50%",
        "effects": [{
            "trigger": "on_attack",
            "effect_type": "conditional_attack_bonus",
            "value": 0.5,
            "condition": "hp_percent < 0.3",
        }],
    },
    "vampiric_ring": {
        "id": "vampiric_ring",
        "name": "吸血戒指",
        "rarity": "rare",
        "description": "造成伤害的15%回血",
        "effects": [{"trigger": "on_deal_damage", "effect_type": "lifesteal", "value": 0.15}],
    },
    "thornmail": {
        "id": "thornmail",
        "name": "荆棘铠甲",
        "rarity": "common",
        "description": "受到攻击时反弹10%伤害",
        "effects": [{"trigger": "on_damaged", "effect_type": "reflect_damage", "value": 0.1}],
    },
    "death_mark": {
        "id": "death_mark",
        "name": "死亡标记",
        "rarity": "legendary",
        "description": "暴击秒杀低血敌人",
        "effects": [{"trigger": "on_crit", "effect_type": "execute", "value": 0.2}],
    },
    "discount_card": {
        "id": "discount_card",
        "name": "折扣卡",
        "rarity": "rare",
        "description": "商店折扣20%",
        "effects": [{"trigger": "on_shop_open", "effect_type": "shop_discount", "value": 0.2}],
    },
}


# ───────────────────────── 8-1: 数据模型 ─────────────────────────

class TestRelicDataModel:

    def test_relic_basic_fields(self):
        relic = Relic("iron_will", MOCK_POOL["iron_will"])
        assert relic.id == "iron_will"
        assert relic.name == "钢铁意志"
        assert relic.rarity == "common"
        assert relic.rarity_enum == Rarity.COMMON
        assert "生命值上限" in relic.description

    def test_relic_effects_parsed(self):
        relic = Relic("blood_rage", MOCK_POOL["blood_rage"])
        assert len(relic.effects) == 1
        eff = relic.effects[0]
        assert isinstance(eff, RelicEffect)
        assert eff.trigger == "on_attack"
        assert eff.effect_type == "conditional_attack_bonus"
        assert eff.value == pytest.approx(0.5)
        assert eff.condition == "hp_percent < 0.3"

    def test_trigger_enum_mapping(self):
        eff = RelicEffect(trigger="on_attack", effect_type="x", value=1)
        assert eff.trigger_enum == RelicTrigger.ON_ATTACK

    def test_unknown_trigger_returns_none(self):
        eff = RelicEffect(trigger="custom_event", effect_type="x", value=1)
        assert eff.trigger_enum is None

    def test_relic_equality_and_hash(self):
        a = Relic("iron_will", MOCK_POOL["iron_will"])
        b = Relic("iron_will", MOCK_POOL["iron_will"])
        c = Relic("blood_rage", MOCK_POOL["blood_rage"])
        assert a == b
        assert a != c
        # 可放进 set
        assert len({a, b, c}) == 2

    def test_rarity_enum_fallback(self):
        cfg = {"name": "X", "rarity": "weird_value", "effects": []}
        relic = Relic("x", cfg)
        # 未知稀有度回退到 COMMON
        assert relic.rarity_enum == Rarity.COMMON

    def test_applies_to(self):
        relic = Relic("blood_rage", MOCK_POOL["blood_rage"])
        assert relic.applies_to("on_attack")
        assert not relic.applies_to("on_pickup")


# ───────────────────────── 8-1: RelicManager 基础 ─────────────────────────

class TestRelicManagerBasics:

    def setup_method(self):
        # 清空全局事件总线，避免测试间相互影响
        event_manager.clear()

    def test_add_relic(self):
        mgr = RelicManager(MOCK_POOL)
        relic = mgr.add_relic("iron_will")
        assert relic is not None
        assert len(mgr.active_relics) == 1
        assert mgr.has_relic("iron_will")

    def test_invalid_relic_ignored(self):
        mgr = RelicManager(MOCK_POOL)
        result = mgr.add_relic("non_existent_relic")
        assert result is None
        assert len(mgr.active_relics) == 0

    def test_duplicate_relic_ignored(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("iron_will")
        result = mgr.add_relic("iron_will")
        assert result is None
        assert len(mgr.active_relics) == 1

    def test_remove_relic(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("iron_will")
        assert mgr.remove_relic("iron_will") is True
        assert not mgr.has_relic("iron_will")
        # 再次移除不存在
        assert mgr.remove_relic("iron_will") is False

    def test_clear_relics(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("iron_will")
        mgr.add_relic("blood_rage")
        mgr.clear()
        assert len(mgr.active_relics) == 0

    def test_get_relic_ids_for_save(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("iron_will")
        mgr.add_relic("blood_rage")
        ids = mgr.get_relic_ids()
        assert set(ids) == {"iron_will", "blood_rage"}


# ───────────────────────── 8-4: 效果派发 ─────────────────────────

class TestRelicEffectDispatch:

    def setup_method(self):
        event_manager.clear()

    def test_on_pickup_max_health_bonus(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("iron_will")
        # 拾取时 _latest_context 应包含 max_health_bonus
        ctx = mgr.latest_context
        assert ctx.get("max_health_bonus") == 20

    def test_lifesteal_modifies_context(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("vampiric_ring")
        ctx = mgr.trigger("on_deal_damage", {"damage": 100})
        assert ctx.get("heal_amount") == 15  # 15% of 100

    def test_reflect_damage(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("thornmail")
        ctx = mgr.trigger("on_damaged", {"damage": 50})
        assert ctx.get("reflect_damage") == 5  # 10% of 50

    def test_conditional_bonus_when_condition_true(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("blood_rage")
        ctx = mgr.trigger("on_attack", {"hp_percent": 0.2})
        # 满足 hp_percent<0.3，触发 +50% damage
        assert ctx.get("damage_multiplier", 1.0) == pytest.approx(1.5)

    def test_conditional_bonus_when_condition_false(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("blood_rage")
        ctx = mgr.trigger("on_attack", {"hp_percent": 0.8})
        # 不满足条件
        assert ctx.get("damage_multiplier", 1.0) == 1.0

    def test_execute_when_low_hp(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("death_mark")
        ctx = mgr.trigger("on_crit", {"target_hp_pct": 0.15})
        assert ctx.get("execute") is True

    def test_execute_when_high_hp(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("death_mark")
        ctx = mgr.trigger("on_crit", {"target_hp_pct": 0.5})
        assert ctx.get("execute") is None

    def test_shop_discount(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("discount_card")
        ctx = mgr.trigger("on_shop_open", {})
        assert ctx.get("shop_discount") == pytest.approx(0.2)

    def test_unknown_event_no_op(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("iron_will")
        ctx = mgr.trigger("on_random_event_no_listener", {"foo": 1})
        # 不应崩溃，只返回原 ctx 副本
        assert ctx == {"foo": 1}


# ───────────────────────── 8-4: 事件总线自动触发 ─────────────────────────

class TestRelicEventBus:

    def setup_method(self):
        event_manager.clear()

    def test_event_bus_triggers_relic(self):
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("vampiric_ring")
        # 通过事件总线发布，应触发遗物
        event_manager.publish("on_deal_damage", damage=200)
        ctx = mgr.latest_context
        assert ctx.get("heal_amount") == 30

    def test_pickup_does_not_double_trigger(self):
        """ON_PICKUP 由 add_relic 直接触发，不应通过事件总线再触发一次"""
        mgr = RelicManager(MOCK_POOL)
        mgr.add_relic("iron_will")
        # 手动再次发布 on_pickup（不应叠加）
        event_manager.publish("on_pickup")
        ctx = mgr.latest_context
        assert ctx.get("max_health_bonus") == 20  # 仍为单次值


# ───────────────────────── 8-4: condition 解析 ─────────────────────────

class TestConditionParsing:

    def test_empty_condition_is_true(self):
        assert _check_condition(None, {}) is True
        assert _check_condition("", {}) is True
        assert _check_condition("always", {}) is True

    def test_lt_condition(self):
        assert _check_condition("hp_percent < 0.3", {"hp_percent": 0.2}) is True
        assert _check_condition("hp_percent < 0.3", {"hp_percent": 0.5}) is False

    def test_gte_condition(self):
        assert _check_condition("combo >= 10", {"combo": 10}) is True
        assert _check_condition("combo >= 10", {"combo": 9}) is False

    def test_eq_string_condition(self):
        assert _check_condition("element == fire", {"element": "fire"}) is True
        assert _check_condition("element == fire", {"element": "ice"}) is False

    def test_named_condition(self):
        assert _check_condition("not_used_this_run", {}) is True
        assert _check_condition("not_used_this_run", {"used_this_run": True}) is False
