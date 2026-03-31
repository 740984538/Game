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


def format_number(n: int) -> str:
    """将大数字格式化为可读字符串，如 1234 → '1,234'"""
    return f"{n:,}"
