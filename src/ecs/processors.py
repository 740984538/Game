"""
处理器（System）注册与优先级管理
对应文档 §10.3.2 系统处理器
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import esper


def register_all_processors(world: "esper.World") -> None:
    """
    向 ECS 世界注册所有处理器，顺序即优先级（数字越小越先执行）
    执行顺序设计原则：输入 → AI → 移动 → 战斗 → Buff → 遗物 → 经济 → 渲染 → UI → 音频
    """
    from src.systems.input_system import InputProcessor
    from src.systems.ai_system import AIProcessor
    from src.systems.movement_system import MovementProcessor
    from src.systems.combat_system import CombatProcessor
    from src.systems.buff_system import BuffProcessor
    from src.systems.relic_system import RelicProcessor
    from src.systems.loot_system import LootProcessor
    from src.systems.economy_system import EconomyProcessor
    from src.systems.render_system import RenderProcessor
    from src.systems.ui_system import UIProcessor
    from src.systems.audio_system import AudioProcessor

    world.add_processor(InputProcessor(),   priority=10)
    world.add_processor(AIProcessor(),      priority=20)
    world.add_processor(MovementProcessor(), priority=30)
    world.add_processor(CombatProcessor(),  priority=40)
    world.add_processor(BuffProcessor(),    priority=50)
    world.add_processor(RelicProcessor(),   priority=60)
    world.add_processor(LootProcessor(),    priority=70)
    world.add_processor(EconomyProcessor(), priority=80)
    world.add_processor(RenderProcessor(),  priority=90)
    world.add_processor(UIProcessor(),      priority=100)
    world.add_processor(AudioProcessor(),   priority=110)
