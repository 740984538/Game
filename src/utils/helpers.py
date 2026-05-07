"""
辅助函数集合
数学计算、几何工具等
"""
from __future__ import annotations
import math
import random
from typing import Tuple


def clamp(value: float, min_val: float, max_val: float) -> float:
    """将数值限制在 [min_val, max_val] 范围内"""
    return max(min_val, min(max_val, value))


def lerp(a: float, b: float, t: float) -> float:
    """线性插值"""
    return a + (b - a) * clamp(t, 0.0, 1.0)


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """计算两点之间的欧氏距离"""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def normalize(x: float, y: float) -> Tuple[float, float]:
    """归一化二维向量，零向量返回 (0, 0)"""
    mag = math.sqrt(x * x + y * y)
    if mag == 0:
        return 0.0, 0.0
    return x / mag, y / mag


def weighted_random_choice(pool: list, weights: list):
    """加权随机选择，对应遗物/战利品概率池（§8.3.2）"""
    total = sum(weights)
    r = random.uniform(0, total)
    cumulative = 0.0
    for item, weight in zip(pool, weights):
        cumulative += weight
        if r <= cumulative:
            return item
    return pool[-1]


def calculate_damage(base: int, attack: int, defense: int,
                     crit_rate: float = 0.0, crit_mult: float = 1.5) -> int:
    """
    基础伤害计算公式（§3.1）
    伤害 = max(1, 攻击 - 防御)，暴击时乘以暴击倍率
    """
    raw = max(1, attack - defense)
    if random.random() < crit_rate:
        raw = int(raw * crit_mult)
    return raw


def calculate_card_damage(base_damage: int, strength: int = 0,
                          is_weak: bool = False, is_vulnerable: bool = False,
                          crit_rate: float = 0.0, crit_mult: float = 1.5,
                          dodge_rate: float = 0.0) -> dict:
    """
    完整卡牌伤害计算 (对应开发计划 6-12)。

    流程:
      1. 基础伤害 + 力量加成
      2. 虚弱减伤 (×0.75)
      3. 闪避检查
      4. 暴击检查 (×暴击倍率)
      5. 易伤增伤 (×1.5)

    返回:
      {
        "damage": int,       最终伤害
        "is_crit": bool,     是否暴击
        "is_dodged": bool,   是否被闪避
      }
    """
    damage = base_damage + strength

    # 虚弱
    if is_weak:
        damage = int(damage * 0.75)

    # 闪避
    if random.random() < dodge_rate:
        return {"damage": 0, "is_crit": False, "is_dodged": True}

    # 暴击
    is_crit = False
    if random.random() < crit_rate:
        damage = int(damage * crit_mult)
        is_crit = True

    # 易伤
    if is_vulnerable:
        damage = int(damage * 1.5)

    return {"damage": max(0, damage), "is_crit": is_crit, "is_dodged": False}


def apply_block(damage: int, block: int) -> tuple:
    """
    格挡吸收伤害 (6-12)。
    返回 (穿透伤害, 剩余格挡)
    """
    absorbed = min(damage, block)
    remaining_damage = damage - absorbed
    remaining_block = block - absorbed
    return remaining_damage, remaining_block


def format_number(n: int) -> str:
    """将大数字格式化为可读字符串，如 1234 → '1,234'"""
    return f"{n:,}"
