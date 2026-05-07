"""
LootManager 单元测试 - 对应开发计划 8-3 (遗物获取)

验证：
  - 房间类型对应的稀有度门槛
  - 普通战斗概率掉落（控制随机种子验证）
  - 精英战斗 100% 1 个遗物
  - BOSS 战斗 3 个候选 + needs_selection
  - 金币按楼层缩放
  - 事件总线触发
"""
import pytest
import random

from src.systems.loot_system import LootManager
from src.core.event_manager import event_manager


MOCK_POOL = {
    "common_a":  {"id": "common_a",  "rarity": "common"},
    "common_b":  {"id": "common_b",  "rarity": "common"},
    "rare_a":    {"id": "rare_a",    "rarity": "rare"},
    "rare_b":    {"id": "rare_b",    "rarity": "rare"},
    "epic_a":    {"id": "epic_a",    "rarity": "epic"},
    "epic_b":    {"id": "epic_b",    "rarity": "epic"},
    "legend_a":  {"id": "legend_a",  "rarity": "legendary"},
}


def _make(seed: int = 42) -> LootManager:
    rng = random.Random(seed)
    return LootManager(relic_pool=MOCK_POOL, rng=rng)


class TestLootManager:

    def setup_method(self):
        event_manager.clear()

    # ── 普通战斗 ─────────────────────────────────────

    def test_combat_room_yields_at_most_one(self):
        mgr = _make(seed=1)
        reward = mgr.roll_combat_reward("combat", floor_number=1)
        assert reward["room_type"] == "combat"
        assert len(reward["relic_choices"]) <= 1
        assert reward["needs_selection"] is False

    def test_combat_room_drops_have_min_rarity_common(self):
        mgr = _make(seed=2)
        reward = mgr.roll_combat_reward("combat", floor_number=1)
        for rid in reward["relic_choices"]:
            assert MOCK_POOL[rid]["rarity"] in ("common", "rare", "epic", "legendary")

    # ── 精英战斗 ─────────────────────────────────────

    def test_elite_always_drops_one_relic(self):
        for seed in range(10):
            mgr = _make(seed=seed)
            reward = mgr.roll_combat_reward("elite", floor_number=2)
            assert len(reward["relic_choices"]) == 1
            assert reward["needs_selection"] is False
            # 精英最低稀有度=rare
            rid = reward["relic_choices"][0]
            assert MOCK_POOL[rid]["rarity"] in ("rare", "epic", "legendary")

    def test_elite_essence_reward(self):
        mgr = _make(seed=1)
        reward = mgr.roll_combat_reward("elite", floor_number=1)
        assert reward["essence"] == 1

    # ── BOSS 战斗 ─────────────────────────────────────

    def test_boss_drops_three_choices(self):
        mgr = _make(seed=3)
        reward = mgr.roll_combat_reward("boss", floor_number=3)
        assert len(reward["relic_choices"]) == 3
        assert reward["needs_selection"] is True
        assert len(set(reward["relic_choices"])) == 3  # 不重复

    def test_boss_min_rarity_epic(self):
        mgr = _make(seed=5)
        reward = mgr.roll_combat_reward("boss", floor_number=4)
        for rid in reward["relic_choices"]:
            assert MOCK_POOL[rid]["rarity"] in ("epic", "legendary")

    def test_boss_essence_reward(self):
        mgr = _make(seed=1)
        reward = mgr.roll_combat_reward("boss", floor_number=1)
        assert reward["essence"] == 3

    # ── 金币缩放 ─────────────────────────────────────

    def test_gold_scales_with_floor(self):
        mgr_low = _make(seed=99)
        mgr_high = _make(seed=99)
        r1 = mgr_low.roll_combat_reward("combat", floor_number=1)
        r5 = mgr_high.roll_combat_reward("combat", floor_number=5)
        # 楼层 5 应当比 楼层 1 金币更多（同种子同基数）
        assert r5["gold"] >= r1["gold"]

    # ── 事件总线 ─────────────────────────────────────

    def test_on_battle_win_event_triggers_loot(self):
        captured = []

        def _listener(reward):
            captured.append(reward)

        event_manager.subscribe("on_loot_generated", _listener)

        mgr = _make(seed=10)
        mgr.set_context(floor_number=2, room_type="elite")

        # 模拟 CombatScene 发布的事件
        event_manager.publish("on_battle_win")

        assert len(captured) == 1
        assert captured[0]["room_type"] == "elite"

    # ── 额外候选 ─────────────────────────────────────

    def test_extra_relic_choices(self):
        mgr = _make(seed=7)
        # boss 默认 3 个，再加 1 个 = 4
        reward = mgr.roll_combat_reward("boss", floor_number=2, extra_relic_choices=1)
        assert len(reward["relic_choices"]) == 4

    # ── 房间类型字符串/枚举兼容 ─────────────────────

    def test_room_type_enum_normalized(self):
        from src.utils.enums import RoomType
        mgr = _make(seed=1)
        reward = mgr.roll_combat_reward(RoomType.ELITE, floor_number=1)
        assert reward["room_type"] == "elite"
