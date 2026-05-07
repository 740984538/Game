"""
粒子系统 - 阶段 9-9

提供：
- :class:`Particle`：单粒子数据
- :class:`ParticleSystem`：粒子管理 + 内置发射器（攻击 / 治疗 / 拾取）

保持简单：无依赖外部资源，使用 pygame 矩形/圆绘制。
所有数值更新可在无 pygame 环境下使用，只有 :meth:`render` 调用 pygame。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False


# ═══════════════════════════════════════════════════════════════════════════════
# 单粒子
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: Tuple[int, int, int]
    size: float
    lifespan: float
    elapsed: float = 0.0
    gravity: float = 0.0
    fade: bool = True
    shape: str = "circle"   # "circle" | "square" | "spark"

    @property
    def alive(self) -> bool:
        return self.elapsed < self.lifespan

    @property
    def alpha(self) -> int:
        if not self.fade or self.lifespan <= 0:
            return 255
        return max(0, int(255 * (1.0 - self.elapsed / self.lifespan)))

    @property
    def current_size(self) -> float:
        if not self.fade or self.lifespan <= 0:
            return self.size
        # 从 size 缩到 0.3 * size
        t = self.elapsed / self.lifespan
        return max(1.0, self.size * (1.0 - 0.7 * t))

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.elapsed += dt


# ═══════════════════════════════════════════════════════════════════════════════
# 粒子系统
# ═══════════════════════════════════════════════════════════════════════════════

class ParticleSystem:
    """
    粒子系统：批量管理粒子的更新与渲染。

    游戏内挂载在战斗场景上，对外暴露三个常用发射器：
        - :meth:`emit_attack`     攻击命中迸发
        - :meth:`emit_heal`       治疗上浮
        - :meth:`emit_pickup`     拾取遗物 / 升级
    """

    MAX_PARTICLES = 600

    def __init__(self) -> None:
        self._particles: List[Particle] = []

    # ── 通用 API ──────────────────────────────────

    def add(self, particle: Particle) -> None:
        if len(self._particles) >= self.MAX_PARTICLES:
            return
        self._particles.append(particle)

    def emit(
        self,
        x: float,
        y: float,
        count: int = 12,
        speed: float = 120.0,
        spread: float = math.tau,
        base_angle: float = 0.0,
        color: Tuple[int, int, int] = (255, 255, 255),
        size: float = 4.0,
        lifespan: float = 0.6,
        gravity: float = 0.0,
        shape: str = "circle",
    ) -> None:
        """
        通用发射：以 (x, y) 为原点向 *base_angle* 方向 ± spread/2 弧度发射 count 个粒子。
        """
        half = spread / 2.0
        for _ in range(count):
            angle = base_angle + random.uniform(-half, half)
            v = speed * random.uniform(0.5, 1.0)
            self.add(Particle(
                x=x, y=y,
                vx=math.cos(angle) * v,
                vy=math.sin(angle) * v,
                color=color,
                size=size * random.uniform(0.7, 1.2),
                lifespan=lifespan * random.uniform(0.7, 1.3),
                gravity=gravity,
                shape=shape,
            ))

    # ── 预设 ──────────────────────────────────────

    def emit_attack(self, x: float, y: float, color=(220, 60, 60)) -> None:
        """攻击命中：四散迸发的暖色火花"""
        self.emit(x, y, count=14, speed=180, color=color, size=4.0, lifespan=0.45,
                  shape="spark", gravity=240.0)

    def emit_heal(self, x: float, y: float) -> None:
        """治疗：向上飘动的绿色粒子"""
        self.emit(x, y, count=10, speed=80, base_angle=-math.pi / 2,
                  spread=math.pi / 3, color=(80, 230, 100),
                  size=4.0, lifespan=0.9, gravity=-30.0, shape="circle")

    def emit_pickup(self, x: float, y: float, color=(255, 215, 0)) -> None:
        """拾取/升级：金色环形闪光"""
        self.emit(x, y, count=24, speed=120, color=color, size=3.0,
                  lifespan=0.7, shape="square", gravity=0.0)

    def emit_block(self, x: float, y: float) -> None:
        """格挡触发：浅蓝小颗粒"""
        self.emit(x, y, count=8, speed=90, color=(180, 200, 255),
                  size=3.0, lifespan=0.4, shape="square")

    # ── 生命周期 ──────────────────────────────────

    def update(self, dt: float) -> None:
        for p in self._particles:
            p.update(dt)
        # 活着的留下来
        self._particles = [p for p in self._particles if p.alive]

    def clear(self) -> None:
        self._particles.clear()

    def __len__(self) -> int:
        return len(self._particles)

    # ── 渲染 ──────────────────────────────────────

    def render(self, surface) -> None:
        if not _pygame_available or not self._particles:
            return
        for p in self._particles:
            color = (p.color[0], p.color[1], p.color[2], p.alpha)
            size = max(1, int(p.current_size))
            if p.shape == "circle" or p.shape == "spark":
                # 用支持 alpha 的 surface 绘制
                surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                pygame.draw.circle(surf, color, (size, size), size)
                surface.blit(surf, (int(p.x) - size, int(p.y) - size))
            else:  # square
                surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                pygame.draw.rect(surf, color, (0, 0, size * 2, size * 2))
                surface.blit(surf, (int(p.x) - size, int(p.y) - size))
