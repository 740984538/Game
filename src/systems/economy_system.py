"""
经济系统 - 对应文档 §3.2 经济系统
处理金币的获取、消耗和货币上限约束
"""
from __future__ import annotations
from src.ecs.components import Wallet, PlayerTag
from src.utils.constants import GOLD_CAP

try:
    import esper
    class EconomyProcessor(esper.Processor):
        def process(self, dt: float) -> None:
            for _ent, (_, wallet) in self.world.get_components(PlayerTag, Wallet):
                wallet.gold = min(wallet.gold, GOLD_CAP)
                wallet.essence = min(wallet.essence, 99)
except ImportError:
    class EconomyProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
