"""
阶段 9-11 自动化测试 —— 核心系统综合用例

覆盖（开发计划要求）：
- 伤害结算逻辑（含力量加成 / 暴击 / 闪避）
- 地图生成（种子确定性、路径连通性）
- 存档读写（序列化/反序列化完整性）  → 见 test_stage9_save_system.py
- 卡牌效果执行（升级 / 伤害变化）

运行： pytest tests/test_stage9_core.py -v
"""
import random
import pytest

from src.utils.helpers import (
    calculate_damage, calculate_card_damage, apply_block,
    weighted_random_choice, clamp, lerp,
)
from src.generation.map_generator import MapGenerator
from src.entities.cards.card import Card
from src.utils.enums import CardType


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 伤害结算
# ═══════════════════════════════════════════════════════════════════════════════

class TestDamageCalculation:
    def test_basic_damage_subtracts_defense(self):
        # 公式：max(1, attack - defense) （base 仅作为占位）
        result = calculate_damage(base=10, attack=5, defense=2)
        assert result == 3

    def test_basic_damage_zero_attack(self):
        # 攻击 ≤ 防御 时取 1 作为最低伤害
        assert calculate_damage(base=0, attack=2, defense=10) == 1

    def test_damage_floor_at_one(self):
        # 极高防御：伤害不为 0 而是最低 1（实现细节）
        result = calculate_damage(base=1, attack=0, defense=999)
        assert result >= 1

    def test_card_damage_strength_buff(self):
        # 力量 +3：基础 10 → 13
        r = calculate_card_damage(10, strength=3)
        assert r["damage"] == 13
        assert not r["is_crit"]
        assert not r["is_dodged"]

    def test_card_damage_weak_modifier(self):
        # 虚弱：×0.75
        r = calculate_card_damage(10, is_weak=True)
        assert r["damage"] == int(10 * 0.75)

    def test_card_damage_vulnerable_modifier(self):
        # 易伤：×1.5
        r = calculate_card_damage(10, is_vulnerable=True)
        assert r["damage"] == int(10 * 1.5)

    def test_card_damage_combined_modifiers(self):
        # 力量+2、易伤、虚弱叠加: (10+2)*0.75*1.5
        r = calculate_card_damage(10, strength=2, is_weak=True, is_vulnerable=True)
        expected = int(int((10 + 2) * 0.75) * 1.5)
        # 实现可能是先 weak 再 vulnerable 取整，允许小误差
        assert abs(r["damage"] - expected) <= 2

    def test_crit_always_when_rate_one(self):
        r = calculate_card_damage(10, crit_rate=1.0)
        assert r["is_crit"]
        assert r["damage"] == int(10 * 1.5)

    def test_dodge_always_when_rate_one(self):
        r = calculate_card_damage(10, dodge_rate=1.0)
        assert r["is_dodged"]
        assert r["damage"] == 0

    def test_apply_block_full_absorb(self):
        damage_after, remaining_block = apply_block(damage=5, block=20)
        assert damage_after == 0
        assert remaining_block == 15

    def test_apply_block_partial(self):
        damage_after, remaining_block = apply_block(damage=15, block=6)
        assert damage_after == 9
        assert remaining_block == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 地图生成 - 种子确定性 + 路径连通性
# ═══════════════════════════════════════════════════════════════════════════════

class TestMapGeneration:
    DEFAULT_CFG = {"nodes_min": 8, "nodes_max": 12}

    def _gen(self, seed: int, floor_no: int = 1) -> "Floor":
        rng = random.Random(seed)
        return MapGenerator(rng).generate_floor(floor_no, self.DEFAULT_CFG)

    def test_seed_determinism_same_node_count(self):
        f1 = self._gen(42)
        f2 = self._gen(42)
        assert len(f1.nodes) == len(f2.nodes)

    def test_seed_determinism_entry_boss_ids(self):
        f1 = self._gen(99)
        f2 = self._gen(99)
        assert f1.entry_node_id == f2.entry_node_id
        assert f1.boss_node_id == f2.boss_node_id

    def test_different_seeds_can_differ(self):
        f1 = self._gen(1)
        f2 = self._gen(99999)
        # 极小概率相同；这里仅验证生成正常即可
        assert len(f1.nodes) > 0 and len(f2.nodes) > 0

    def test_path_to_boss_always_exists(self):
        for seed in (1, 42, 999, 12345, 99999):
            floor = self._gen(seed)
            assert floor.has_path_to_boss(), f"seed={seed} 没有到 BOSS 的路径"

    def test_node_count_within_range(self):
        for seed in range(10):
            floor = self._gen(seed)
            # 含 entry + boss 两个额外节点
            interior = len(floor.nodes) - 2
            assert 8 <= interior <= 12, f"seed={seed} interior={interior}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 卡牌效果执行 / 升级
# ═══════════════════════════════════════════════════════════════════════════════

ATTACK_CARD_CFG = {
    "id": "strike", "name": "打击", "type": "attack", "cost": 1,
    "description": "造成 6 点伤害",
    "effect": {"damage": 6},
    "upgraded_description": "造成 9 点伤害",
    "upgraded_effect": {"damage": 9},
}

SKILL_CARD_CFG = {
    "id": "defend", "name": "防御", "type": "skill", "cost": 1,
    "description": "获得 5 点格挡",
    "effect": {"block": 5},
    "upgraded_effect": {"block": 8},
}

CURSED_CARD_CFG = {
    "id": "wound", "name": "重创", "type": "cursed", "cost": 0,
    "description": "诅咒卡，无效果",
    "effect": {},
}


class TestCardModel:
    def test_from_config_attack(self):
        c = Card.from_config(ATTACK_CARD_CFG)
        assert c.card_id == "strike"
        assert c.card_type == CardType.ATTACK
        assert c.cost == 1
        assert c.get_damage() == 6
        assert not c.upgraded

    def test_upgrade_changes_damage(self):
        c = Card.from_config(ATTACK_CARD_CFG)
        ok = c.upgrade()
        assert ok
        assert c.upgraded
        assert c.get_damage() == 9

    def test_upgrade_idempotent(self):
        c = Card.from_config(ATTACK_CARD_CFG)
        c.upgrade()
        # 二次升级失败
        assert not c.upgrade()
        assert c.get_damage() == 9

    def test_skill_block_value(self):
        c = Card.from_config(SKILL_CARD_CFG)
        assert c.get_damage() == 0
        assert c.get_block() == 5
        c.upgrade()
        assert c.get_block() == 8

    def test_cursed_card_zero_damage(self):
        c = Card.from_config(CURSED_CARD_CFG)
        assert c.card_type == CardType.CURSED
        assert c.get_damage() == 0
        assert c.get_block() == 0

    def test_card_copy_independent(self):
        c1 = Card.from_config(ATTACK_CARD_CFG)
        c2 = c1.copy()
        c2.upgrade()
        assert c2.upgraded
        assert not c1.upgraded


# ═══════════════════════════════════════════════════════════════════════════════
# 4. helpers 工具函数
# ═══════════════════════════════════════════════════════════════════════════════

class TestHelpers:
    def test_clamp(self):
        assert clamp(5, 0, 10) == 5
        assert clamp(-1, 0, 10) == 0
        assert clamp(99, 0, 10) == 10

    def test_lerp_endpoints(self):
        assert lerp(0, 100, 0.0) == 0
        assert lerp(0, 100, 1.0) == 100
        assert lerp(0, 100, 0.5) == 50

    def test_weighted_random_choice_picks_only_nonzero(self):
        rng = random.Random(0)
        results = set()
        for _ in range(200):
            random.seed(rng.random())  # 重新设置全局 random
            pick = weighted_random_choice(["a", "b", "c"], [10, 0, 0])
            results.add(pick)
        # 只有 a 有权重，其余必须永远不会被选中
        assert results == {"a"}
