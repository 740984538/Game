"""
音频系统 - 对应文档 §10.1.2 音效处理
根据游戏事件播放对应音效
"""
from __future__ import annotations
from src.core.event_manager import event_manager
from src.core.resource_manager import resource_manager

try:
    import esper
    class AudioProcessor(esper.Processor):
        def process(self, dt: float) -> None:
            # 音效通过事件总线触发，此处无需每帧轮询
            pass
except ImportError:
    class AudioProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
