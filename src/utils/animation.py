"""
动画 / 过渡效果工具 - 阶段 9-8

提供：
- :class:`Easing`：常用缓动函数
- :class:`Tween`：单值/向量缓动器
- :class:`FloatingNumber` / :class:`FloatingNumberManager`：伤害飘字
- :class:`ScreenShake`：屏幕震动控制器

所有类都不依赖 pygame.image，仅在 :meth:`render` 中调用 pygame 接口；
若运行环境无 pygame（如单元测试），数值更新逻辑仍可正常使用。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False


# ═══════════════════════════════════════════════════════════════════════════════
# Easing
# ═══════════════════════════════════════════════════════════════════════════════

class Easing:
    """常用缓动函数。所有函数签名 ``f(t: float) -> float``，t ∈ [0, 1]。"""

    @staticmethod
    def linear(t: float) -> float:
        return t

    @staticmethod
    def ease_in(t: float) -> float:
        return t * t

    @staticmethod
    def ease_out(t: float) -> float:
        return 1 - (1 - t) * (1 - t)

    @staticmethod
    def ease_in_out(t: float) -> float:
        if t < 0.5:
            return 2 * t * t
        return 1 - (-2 * t + 2) ** 2 / 2

    @staticmethod
    def ease_out_back(t: float) -> float:
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

    @staticmethod
    def ease_out_cubic(t: float) -> float:
        return 1 - (1 - t) ** 3


# ═══════════════════════════════════════════════════════════════════════════════
# Tween
# ═══════════════════════════════════════════════════════════════════════════════

class Tween:
    """
    单值或多值缓动器。

    用法::

        tw = Tween(start=(0, 0), end=(100, 50), duration=0.5,
                   easing=Easing.ease_out_cubic, on_complete=on_done)
        ...
        # 每帧
        tw.update(dt)
        x, y = tw.value
        if tw.finished: ...
    """

    def __init__(
        self,
        start,
        end,
        duration: float,
        easing: Callable[[float], float] = Easing.linear,
        on_complete: Optional[Callable[[], None]] = None,
        delay: float = 0.0,
    ) -> None:
        self._start = start
        self._end = end
        self._duration = max(0.001, float(duration))
        self._easing = easing
        self._on_complete = on_complete
        self._delay = max(0.0, float(delay))
        self._elapsed = 0.0
        self._finished = False
        self._is_seq = isinstance(start, (tuple, list))

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def progress(self) -> float:
        if self._elapsed <= self._delay:
            return 0.0
        t = (self._elapsed - self._delay) / self._duration
        return max(0.0, min(1.0, t))

    @property
    def value(self):
        t = self._easing(self.progress)
        if self._is_seq:
            return tuple(
                a + (b - a) * t for a, b in zip(self._start, self._end)
            )
        return self._start + (self._end - self._start) * t

    def update(self, dt: float) -> None:
        if self._finished:
            return
        self._elapsed += dt
        if self._elapsed >= self._delay + self._duration:
            self._finished = True
            if self._on_complete:
                try:
                    self._on_complete()
                except Exception:
                    pass

    def reset(self) -> None:
        self._elapsed = 0.0
        self._finished = False


# ═══════════════════════════════════════════════════════════════════════════════
# 伤害飘字
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FloatingNumber:
    """
    伤害/治疗飘字。从起始位置上浮 + 渐隐。

    color 默认红色，治疗可传 (0, 220, 0)；暴击可传 (255, 200, 0) 并放大字体。
    """
    text: str
    x: float
    y: float
    color: Tuple[int, int, int] = (220, 60, 60)
    duration: float = 1.0
    rise: float = 40.0          # 像素
    font_size: int = 24
    elapsed: float = 0.0
    crit: bool = False

    @property
    def alive(self) -> bool:
        return self.elapsed < self.duration

    @property
    def alpha(self) -> int:
        if self.duration <= 0:
            return 255
        # 后半段渐隐
        t = self.elapsed / self.duration
        if t < 0.5:
            return 255
        fade = 1.0 - (t - 0.5) * 2.0
        return max(0, int(fade * 255))

    @property
    def offset_y(self) -> float:
        if self.duration <= 0:
            return 0.0
        t = min(1.0, self.elapsed / self.duration)
        # ease_out
        return self.rise * (1 - (1 - t) * (1 - t))

    def update(self, dt: float) -> None:
        self.elapsed += dt


class FloatingNumberManager:
    """
    伤害飘字管理器。供战斗场景调用 ``spawn(...)`` 添加飘字，
    每帧调用 ``update(dt)`` 与 ``render(surface, font_provider)``。
    """

    def __init__(self) -> None:
        self._items: List[FloatingNumber] = []

    def spawn(
        self,
        text: str,
        x: float,
        y: float,
        color: Tuple[int, int, int] = (220, 60, 60),
        duration: float = 1.0,
        rise: float = 40.0,
        font_size: int = 24,
        crit: bool = False,
    ) -> FloatingNumber:
        item = FloatingNumber(
            text=str(text), x=float(x), y=float(y),
            color=color, duration=duration, rise=rise,
            font_size=font_size, crit=crit,
        )
        self._items.append(item)
        return item

    def spawn_damage(self, value: int, x: float, y: float, *, crit: bool = False) -> FloatingNumber:
        text = f"-{int(value)}"
        if crit:
            return self.spawn(text + "!", x, y, color=(255, 200, 0), font_size=32, crit=True)
        return self.spawn(text, x, y, color=(220, 60, 60), font_size=24)

    def spawn_heal(self, value: int, x: float, y: float) -> FloatingNumber:
        return self.spawn(f"+{int(value)}", x, y, color=(80, 220, 80), font_size=24)

    def spawn_block(self, value: int, x: float, y: float) -> FloatingNumber:
        return self.spawn(f"格挡 {int(value)}", x, y, color=(180, 180, 220), font_size=20)

    def update(self, dt: float) -> None:
        for it in self._items:
            it.update(dt)
        self._items = [it for it in self._items if it.alive]

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)

    def render(self, surface, font_provider: Callable[[int], "pygame.font.Font"]) -> None:
        """
        ``font_provider(size)`` 返回对应字号的 pygame 字体。
        """
        if not _pygame_available:
            return
        for it in self._items:
            font = font_provider(it.font_size)
            surf = font.render(it.text, True, it.color)
            alpha = it.alpha
            if alpha < 255:
                surf = surf.copy()
                surf.set_alpha(alpha)
            rect = surf.get_rect(center=(int(it.x), int(it.y - it.offset_y)))
            surface.blit(surf, rect)


# ═══════════════════════════════════════════════════════════════════════════════
# 屏幕震动
# ═══════════════════════════════════════════════════════════════════════════════

class ScreenShake:
    """
    屏幕震动效果。trigger() 触发后产生衰减的随机位移，
    每帧调用 ``update(dt)`` 然后用 ``offset`` 在 blit 时偏移整屏。
    """

    def __init__(self) -> None:
        self._intensity = 0.0
        self._duration = 0.0
        self._elapsed = 0.0
        self._offset_x = 0.0
        self._offset_y = 0.0

    def trigger(self, intensity: float = 8.0, duration: float = 0.25) -> None:
        # 多次触发取最大值，避免被弱效叠加削弱
        if duration > self._duration - self._elapsed or intensity > self._intensity:
            self._intensity = max(self._intensity, float(intensity))
            self._duration = float(duration)
            self._elapsed = 0.0

    @property
    def is_shaking(self) -> bool:
        return self._duration > 0 and self._elapsed < self._duration

    @property
    def offset(self) -> Tuple[int, int]:
        return int(self._offset_x), int(self._offset_y)

    def update(self, dt: float) -> None:
        if not self.is_shaking:
            self._offset_x = self._offset_y = 0.0
            return
        self._elapsed += dt
        progress = min(1.0, self._elapsed / self._duration)
        cur = self._intensity * (1.0 - progress)  # 线性衰减
        self._offset_x = random.uniform(-cur, cur)
        self._offset_y = random.uniform(-cur, cur)
        if progress >= 1.0:
            self._duration = 0.0
            self._intensity = 0.0
            self._offset_x = self._offset_y = 0.0

    def stop(self) -> None:
        self._duration = 0.0
        self._intensity = 0.0
        self._elapsed = 0.0
        self._offset_x = self._offset_y = 0.0
