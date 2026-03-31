"""
种子管理器 - 对应文档 §8.3.1 种子系统
确保相同种子产生相同地图（每日挑战的基础）
"""
from __future__ import annotations
import random
import time


class SeedManager:
    """
    管理随机种子，支持：
    - 自动生成随机种子
    - 手动指定种子（自定义模式 §7.4.1）
    - 种子分享（转为可读字符串）
    """

    def __init__(self) -> None:
        self._seed: int = 0
        self._rng: random.Random = random.Random()

    def new_seed(self) -> int:
        """生成新的随机种子"""
        self._seed = int(time.time() * 1000) & 0xFFFFFFFF
        self._rng.seed(self._seed)
        return self._seed

    def set_seed(self, seed: int) -> None:
        """使用指定种子"""
        self._seed = seed
        self._rng.seed(seed)

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def rng(self) -> random.Random:
        return self._rng

    def daily_seed(self) -> int:
        """
        根据当天日期生成每日挑战种子（§7.2.1）
        同一天所有玩家得到相同种子
        """
        from datetime import date
        today = date.today()
        seed = int(today.strftime("%Y%m%d"))
        self.set_seed(seed)
        return seed
