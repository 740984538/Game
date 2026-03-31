"""
战利品生成器 - 对应文档 §4.1.2 奖励设计 / §5.2.2 遗物稀有度
加权随机从遗物池中抽取奖励
"""
from __future__ import annotations
import random
from typing import List, Dict

# 稀有度权重（§5.2.2）
RARITY_WEIGHTS: Dict[str, float] = {
    "common":    60.0,
    "rare":      30.0,
    "epic":       9.0,
    "legendary":  1.0,
}


class LootGenerator:
    """根据规则生成战利品（遗物/金币/精华）"""

    def __init__(self, rng: random.Random, relic_pool: Dict[str, dict]) -> None:
        self._rng = rng
        self._relic_pool = relic_pool  # {relic_id: relic_config}

    def roll_relic(self, min_rarity: str = "common") -> str:
        """
        从遗物池中抽取一个遗物ID，支持最低稀有度约束。
        对应文档 §4.1.2（精英房间必掉遗物）
        """
        rarity_order = ["common", "rare", "epic", "legendary"]
        min_idx = rarity_order.index(min_rarity)
        eligible = {k: v for k, v in self._relic_pool.items()
                    if rarity_order.index(v["rarity"]) >= min_idx}
        if not eligible:
            eligible = self._relic_pool

        # 先按稀有度权重选稀有度，再从该稀有度中随机选遗物
        rarities = [r for r in rarity_order if r in {v["rarity"] for v in eligible.values()}]
        weights = [RARITY_WEIGHTS[r] for r in rarities]
        chosen_rarity = self._rng.choices(rarities, weights=weights, k=1)[0]

        candidates = [rid for rid, cfg in eligible.items() if cfg["rarity"] == chosen_rarity]
        return self._rng.choice(candidates)

    def roll_gold(self, min_val: int, max_val: int) -> int:
        """生成金币掉落数量"""
        return self._rng.randint(min_val, max_val)

    def roll_n_relics(self, n: int, min_rarity: str = "common") -> List[str]:
        """生成 n 个不重复遗物供玩家选择（对应 BOSS 奖励 3选1）"""
        chosen = []
        original_pool = self._relic_pool
        remaining_pool = dict(original_pool)
        for _ in range(min(n, len(remaining_pool))):
            self._relic_pool = remaining_pool
            relic_id = self.roll_relic(min_rarity)
            chosen.append(relic_id)
            remaining_pool.pop(relic_id, None)
        self._relic_pool = original_pool
        return chosen
