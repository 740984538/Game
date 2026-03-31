"""
角色属性计算 - 对应文档 §3.1 数值设计
所有最终属性都经过遗物加成叠加后计算
"""
from __future__ import annotations
from src.utils.constants import MAX_CRIT_RATE, MAX_DODGE_RATE, MAX_COOLDOWN_REDUCTION
from src.utils.helpers import clamp


def calculate_final_stats(base_stats: dict, relic_bonuses: dict) -> dict:
    """
    将基础属性与遗物加成合并，返回最终属性字典。
    对应文档 §3.1.2 单局数值范围规范（上限约束）
    """
    final = dict(base_stats)

    final["attack"] = int(
        final.get("attack", 10) * (1 + relic_bonuses.get("attack_percent", 0))
        + relic_bonuses.get("attack_flat", 0)
    )
    final["defense"] = max(0, final.get("defense", 0) + relic_bonuses.get("defense_flat", 0))
    final["max_health"] = final.get("health", 80) + relic_bonuses.get("max_health_flat", 0)
    final["crit_rate"] = clamp(
        final.get("crit_rate", 0.05) + relic_bonuses.get("crit_rate", 0),
        0.0, MAX_CRIT_RATE
    )
    final["dodge_rate"] = clamp(
        final.get("dodge_rate", 0.0) + relic_bonuses.get("dodge_rate", 0),
        0.0, MAX_DODGE_RATE
    )
    return final
