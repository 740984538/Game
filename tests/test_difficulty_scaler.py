"""
DifficultyScaler 单元测试 - 对应开发计划 8-10 (游戏难度曲线)

验证：
  - 楼层缩放（HP / 攻击 / 防御）按预设系数
  - 难度缩放（hp_mult / atk_mult）从配置读取
  - scale_enemy_stats 综合两者
  - scale_enemy_config 返回新字典且不修改原始
  - 商店价格按楼层 + 难度缩放
  - 精英比例随楼层增长且封顶
  - 遗物掉落概率随楼层增长
"""
import pytest
from src.generation.difficulty_scaler import (
    DifficultyScaler, ScaledStats,
    FLOOR_HP_PER_LEVEL, FLOOR_ATK_PER_LEVEL, FLOOR_DEF_PER_LEVEL,
    ELITE_BASE_RATIO, ELITE_PER_FLOOR, ELITE_MAX_RATIO,
    RELIC_BASE_DROP_CHANCE, RELIC_DROP_FLOOR_BONUS, RELIC_DROP_MAX,
    SHOP_PRICE_FLOOR_MULT, SHOP_PRICE_DIFFICULTY_MULT,
)


class TestFloorScaling:

    def test_floor_1_baseline(self):
        s = DifficultyScaler()
        assert s.floor_hp_mult(1) == pytest.approx(1.0)
        assert s.floor_atk_mult(1) == pytest.approx(1.0)
        assert s.floor_def_mult(1) == pytest.approx(1.0)

    def test_floor_5_scales(self):
        s = DifficultyScaler()
        assert s.floor_hp_mult(5) == pytest.approx(1.0 + 4 * FLOOR_HP_PER_LEVEL)
        assert s.floor_atk_mult(5) == pytest.approx(1.0 + 4 * FLOOR_ATK_PER_LEVEL)
        assert s.floor_def_mult(5) == pytest.approx(1.0 + 4 * FLOOR_DEF_PER_LEVEL)

    def test_floor_below_1_treated_as_1(self):
        s = DifficultyScaler()
        assert s.floor_hp_mult(0) == pytest.approx(1.0)
        assert s.floor_hp_mult(-2) == pytest.approx(1.0)


class TestDifficultyMultipliers:

    def test_known_difficulties(self):
        s = DifficultyScaler()
        assert s.difficulty_hp_mult(0) == pytest.approx(1.0)
        assert s.difficulty_hp_mult(1) == pytest.approx(1.2)
        assert s.difficulty_hp_mult(4) == pytest.approx(3.0)
        assert s.difficulty_atk_mult(2) == pytest.approx(1.2)

    def test_unknown_difficulty_returns_default(self):
        s = DifficultyScaler()
        assert s.difficulty_hp_mult(999) == pytest.approx(1.0)

    def test_get_difficulty_name(self):
        s = DifficultyScaler()
        assert s.get_difficulty_name(1) == "普通"
        assert s.get_difficulty_name(3) == "噩梦"

    def test_get_revive_count(self):
        s = DifficultyScaler()
        assert s.get_revive_count(0) == 1   # 新手有复活
        assert s.get_revive_count(1) == 0


class TestScaleEnemyStats:

    def test_baseline_no_change(self):
        s = DifficultyScaler()
        result = s.scale_enemy_stats(100, 10, 5, floor=1, difficulty=0)
        assert isinstance(result, ScaledStats)
        assert result.health == 100
        assert result.attack == 10
        assert result.defense == 5

    def test_floor_5_difficulty_2(self):
        s = DifficultyScaler()
        result = s.scale_enemy_stats(100, 10, 5, floor=5, difficulty=2)
        # hp = int(100 * 1.4 * 1.5) ≈ 209 或 210（浮点截断）
        assert result.health in (209, 210)
        # attack = int(10 * 1.32 * 1.2) ≈ 15
        assert result.attack == 15
        # defense = int(5 * 1.2) = 6
        assert result.defense == 6

    def test_minimum_values_protected(self):
        s = DifficultyScaler()
        # 极小输入不应变 0 或负数
        result = s.scale_enemy_stats(1, 1, 0, floor=1, difficulty=4)
        assert result.health >= 1
        assert result.attack >= 1
        assert result.defense >= 0


class TestScaleEnemyConfig:

    def test_returns_new_dict_without_mutating_input(self):
        s = DifficultyScaler()
        original = {
            "id": "skeleton",
            "base_stats": {"health": 30, "attack": 8, "defense": 2},
        }
        scaled = s.scale_enemy_config(original, floor=3, difficulty=1)
        # 原始不变
        assert original["base_stats"]["health"] == 30
        # 新字典已缩放
        assert scaled["base_stats"]["health"] > 30

    def test_preserves_other_fields(self):
        s = DifficultyScaler()
        original = {
            "id": "skeleton",
            "name": "骷髅",
            "ai_pattern": "melee_aggressive",
            "base_stats": {"health": 30, "attack": 8, "defense": 2},
        }
        scaled = s.scale_enemy_config(original, floor=2, difficulty=1)
        assert scaled["id"] == "skeleton"
        assert scaled["name"] == "骷髅"
        assert scaled["ai_pattern"] == "melee_aggressive"


class TestShopPriceScaling:

    def test_baseline(self):
        s = DifficultyScaler()
        assert s.shop_price_mult(1, 0) == pytest.approx(1.0)

    def test_floor_increases_price(self):
        s = DifficultyScaler()
        m1 = s.shop_price_mult(1, 1)
        m5 = s.shop_price_mult(5, 1)
        assert m5 > m1

    def test_difficulty_increases_price(self):
        s = DifficultyScaler()
        m_low = s.shop_price_mult(1, 0)
        m_high = s.shop_price_mult(1, 4)
        assert m_high > m_low

    def test_scale_price(self):
        s = DifficultyScaler()
        # 100 在楼层 1 难度 0 应保持 100
        assert s.scale_price(100, floor=1, difficulty=0) == 100
        # 楼层 3 难度 1
        # mult = (1 + 2*0.15) * (1 + 1*0.20) = 1.3 * 1.2 = 1.56
        assert s.scale_price(100, floor=3, difficulty=1) == 156

    def test_minimum_one_gold(self):
        s = DifficultyScaler()
        assert s.scale_price(0, floor=1, difficulty=0) == 1


class TestEliteRatio:

    def test_floor_1_baseline(self):
        s = DifficultyScaler()
        assert s.elite_ratio(1) == pytest.approx(ELITE_BASE_RATIO)

    def test_floor_increases_ratio(self):
        s = DifficultyScaler()
        assert s.elite_ratio(3) == pytest.approx(
            ELITE_BASE_RATIO + 2 * ELITE_PER_FLOOR
        )

    def test_capped_at_max(self):
        s = DifficultyScaler()
        assert s.elite_ratio(99) == pytest.approx(ELITE_MAX_RATIO)


class TestRelicDropChance:

    def test_floor_1_baseline(self):
        s = DifficultyScaler()
        assert s.relic_drop_chance(1) == pytest.approx(RELIC_BASE_DROP_CHANCE)

    def test_floor_increases_chance(self):
        s = DifficultyScaler()
        c1 = s.relic_drop_chance(1)
        c5 = s.relic_drop_chance(5)
        assert c5 > c1

    def test_capped_at_max(self):
        s = DifficultyScaler()
        assert s.relic_drop_chance(99) == pytest.approx(RELIC_DROP_MAX)


class TestFromConfig:

    def test_load_from_real_config(self):
        """从真实 config/game_config.yaml 加载难度数据"""
        s = DifficultyScaler.from_config()
        assert s.get_difficulty_name(0) == "新手"
        assert s.difficulty_hp_mult(2) == pytest.approx(1.5)
        assert s.difficulty_atk_mult(3) == pytest.approx(1.5)


class TestGoldRewardMult:

    def test_baseline(self):
        s = DifficultyScaler()
        assert s.gold_reward_mult(1, 1) == pytest.approx(1.0)

    def test_higher_difficulty_more_gold(self):
        s = DifficultyScaler()
        assert s.gold_reward_mult(1, 4) == pytest.approx(1.3)
