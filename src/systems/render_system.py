"""
渲染系统 - 对应文档 §6.1.1 界面层级（Layer 0-4）
按层级顺序渲染所有 Renderable 实体
"""
from __future__ import annotations
from src.ecs.components import Renderable, Position
from src.core.resource_manager import resource_manager

try:
    import esper
    import pygame

    class RenderProcessor(esper.Processor):
        def __init__(self, surface) -> None:
            super().__init__()
            self.surface = surface

        def process(self, dt: float) -> None:
            # 按层级排序后渲染
            renderables = [
                (layer, pos, rend)
                for _ent, (rend, pos) in self.world.get_components(Renderable, Position)
                if rend.visible
                for layer in [rend.layer]
            ]
            renderables.sort(key=lambda x: x[0])
            for _layer, pos, rend in renderables:
                img = resource_manager.get_image(rend.sprite_key)
                if img:
                    self.surface.blit(img, (int(pos.x), int(pos.y)))
except ImportError:
    class RenderProcessor:  # type: ignore[no-redef]
        def __init__(self, surface=None) -> None:
            pass
        def process(self, dt: float) -> None:
            pass
