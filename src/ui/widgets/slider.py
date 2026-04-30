"""
滑块组件（用于音量等数值调节）
阶段2-9 辅助组件
"""
from __future__ import annotations
from typing import Callable, Optional, Tuple

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.ui.widgets.base_widget import UIComponent
from src.utils.constants import (
    COLOR_BG_DARK, COLOR_DIVIDER, COLOR_TEXT_PRIMARY, COLOR_WHITE,
)


class Slider(UIComponent):
    """
    水平滑块，value 范围 [min_val, max_val]。
    on_change(value) 在值变化时回调。
    """

    _TRACK_H   = 6
    _THUMB_R   = 10    # 圆形滑块半径

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        min_val: float = 0.0,
        max_val: float = 1.0,
        value:   float = 0.5,
        on_change: Optional[Callable[[float], None]] = None,
        track_color: Tuple[int, int, int] = COLOR_DIVIDER,
        fill_color:  Tuple[int, int, int] = COLOR_TEXT_PRIMARY,
        thumb_color: Tuple[int, int, int] = COLOR_WHITE,
    ) -> None:
        super().__init__(x, y, width, height)
        self._min_val    = min_val
        self._max_val    = max_val
        self._value      = max(min_val, min(max_val, value))
        self._on_change  = on_change
        self._track_color = track_color
        self._fill_color  = fill_color
        self._thumb_color = thumb_color
        self._dragging    = False

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = max(self._min_val, min(self._max_val, v))

    def _ratio(self) -> float:
        span = self._max_val - self._min_val
        if span == 0:
            return 0.0
        return (self._value - self._min_val) / span

    def _thumb_cx(self) -> int:
        return self._x + self._THUMB_R + int(self._ratio() * (self._width - 2 * self._THUMB_R))

    def _track_cy(self) -> int:
        return self._y + self._height // 2

    def _pos_to_value(self, px: int) -> float:
        usable = self._width - 2 * self._THUMB_R
        if usable <= 0:
            return self._min_val
        ratio = (px - self._x - self._THUMB_R) / usable
        ratio = max(0.0, min(1.0, ratio))
        return self._min_val + ratio * (self._max_val - self._min_val)

    def handle_event(self, event) -> bool:
        if not self._visible or not self._enabled or not _pygame_available:
            return False

        cy = self._track_cy()
        tcx = self._thumb_cx()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 点击滑块或轨道
            if self.contains_point(*event.pos):
                self._dragging = True
                self._value = self._pos_to_value(event.pos[0])
                if self._on_change:
                    self._on_change(self._value)
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if self._dragging:
                self._value = self._pos_to_value(event.pos[0])
                if self._on_change:
                    self._on_change(self._value)
                return True

        return False

    def render(self, surface) -> None:
        if not self._visible or not _pygame_available:
            return

        cy = self._track_cy()
        r  = self._THUMB_R

        # 轨道背景
        track_rect = pygame.Rect(
            self._x + r, cy - self._TRACK_H // 2,
            self._width - 2 * r, self._TRACK_H,
        )
        pygame.draw.rect(surface, self._track_color, track_rect, border_radius=3)

        # 已填充部分
        fill_w = int(self._ratio() * (self._width - 2 * r))
        if fill_w > 0:
            fill_rect = pygame.Rect(
                self._x + r, cy - self._TRACK_H // 2,
                fill_w, self._TRACK_H,
            )
            pygame.draw.rect(surface, self._fill_color, fill_rect, border_radius=3)

        # 滑块圆形
        tcx = self._thumb_cx()
        pygame.draw.circle(surface, self._thumb_color, (tcx, cy), r)
        pygame.draw.circle(surface, self._fill_color,  (tcx, cy), r, 2)

        self._render_children(surface)
