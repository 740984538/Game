"""
战斗系统单元测试
验证伤害计算、暴击、闪避逻辑
对应文档 §3.1.2 数值范围规范
"""
import pytest
from src.utils.helpers import calculate_damage, clamp


class TestDamageCalculation:
    def test_basic_damage(self):
        """基础伤害 = max(1, 攻击 - 防御)"""
        dmg = calculate_damage(base=0, attack=15, defense=5, crit_rate=0.0)
        assert dmg == 10

    def test_minimum_damage_is_1(self):
        """防御高于攻击时，伤害最低为1"""
        dmg = calculate_damage(base=0, attack=5, defense=20, crit_rate=0.0)
        assert dmg >= 1

    def test_crit_multiplier(self):
        """100%暴击率时，伤害应为普通伤害的 crit_mult 倍"""
        import random
        random.seed(42)
        dmg = calculate_damage(base=0, attack=20, defense=0,
                               crit_rate=1.0, crit_mult=2.0)
        assert dmg == 40

    def test_clamp(self):
        assert clamp(150.0, 0.0, 100.0) == 100.0
        assert clamp(-10.0, 0.0, 100.0) == 0.0
        assert clamp(50.0, 0.0, 100.0) == 50.0
