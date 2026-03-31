"""
输入系统 - 对应文档 §6.2.1 战斗操作（WASD移动、空格闪避、数字键卡牌）
"""
from __future__ import annotations
from src.ecs.components import Velocity, PlayerTag, CardHolder

try:
    import pygame
    import esper

    _KEY_SPEED = 200.0   # 像素/秒

    class InputProcessor(esper.Processor):
        def process(self, dt: float) -> None:
            keys = pygame.key.get_pressed()
            for _ent, (_, vel) in self.world.get_components(PlayerTag, Velocity):
                vel.vx = 0.0
                vel.vy = 0.0
                if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                    vel.vx = -_KEY_SPEED
                if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                    vel.vx = _KEY_SPEED
                if keys[pygame.K_w] or keys[pygame.K_UP]:
                    vel.vy = -_KEY_SPEED
                if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                    vel.vy = _KEY_SPEED
except ImportError:
    class InputProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
