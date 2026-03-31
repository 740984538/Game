"""
战利品生成单元测试
验证遗物稀有度概率分布
对应文档 §5.2.2 遗物稀有度
"""
import pytest
import random
from src.generation.loot_generator import LootGenerator

MOCK_RELIC_POOL = {
    "relic_common_1": {"id": "relic_common_1", "rarity": "common"},
    "relic_common_2": {"id": "relic_common_2", "rarity": "common"},
    "relic_rare_1":   {"id": "relic_rare_1",   "rarity": "rare"},
    "relic_epic_1":   {"id": "relic_epic_1",   "rarity": "epic"},
    "relic_legend_1": {"id": "relic_legend_1", "rarity": "legendary"},
}


class TestLootGeneration:
    def test_roll_returns_valid_relic(self):
        rng = random.Random(42)
        gen = LootGenerator(rng, MOCK_RELIC_POOL)
        relic_id = gen.roll_relic()
        assert relic_id in MOCK_RELIC_POOL

    def test_min_rarity_constraint(self):
        """min_rarity=epic 时不能返回 common/rare 遗物"""
        rng = random.Random(42)
        gen = LootGenerator(rng, MOCK_RELIC_POOL)
        for _ in range(20):
            relic_id = gen.roll_relic(min_rarity="epic")
            assert MOCK_RELIC_POOL[relic_id]["rarity"] in ("epic", "legendary")

    def test_roll_n_no_duplicates(self):
        """roll_n_relics 返回不重复的遗物"""
        rng = random.Random(42)
        gen = LootGenerator(rng, MOCK_RELIC_POOL)
        relics = gen.roll_n_relics(3)
        assert len(relics) == len(set(relics))
