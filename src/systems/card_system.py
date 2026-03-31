"""
卡牌系统 - 对应文档 §5.3 卡牌/技能系统
处理卡牌使用、能量消耗、升级
"""
from __future__ import annotations
from src.ecs.components import CardHolder, PlayerTag

try:
    import esper
    class CardProcessor(esper.Processor):
        def process(self, dt: float) -> None:
            # TODO: 每回合恢复能量，处理卡牌使用输入
            pass
except ImportError:
    class CardProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
