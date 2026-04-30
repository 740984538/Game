"""
按钮组件
对应文档 §6.3 UI设计规范，阶段2-2
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
    COLOR_BG_LIGHT, COLOR_TEXT_PRIMARY, COLOR_WHITE,
    COLOR_DIVIDER, FONT_SIZE_BODY,
)


class Button(UIComponent):
    """
    矩形按钮组件，支持三种视觉状态：
    - 普通(normal)、悬停(hover)、按下(pressed)、禁用(disabled)
    """

    # 默认颜色方案
    _DEFAULT_NORMAL_BG   = COLOR_BG_LIGHT         # (22,33,62)
    _DEFAULT_HOVER_BG    = (40, 60, 100)
    _DEFAULT_PRESSED_BG  = (15, 25, 50)
    _DEFAULT_DISABLED_BG = (30, 30, 30)
    _DEFAULT_BORDER      = COLOR_DIVIDER           # (15,52,96)
    _DEFAULT_HOVER_BORDER = COLOR_TEXT_PRIMARY     # (233,69,96)
    _DEFAULT_TEXT_COLOR  = COLOR_WHITE
    _DEFAULT_DISABLED_TEXT = (100, 100, 100)

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str = "",
        font_size: int = FONT_SIZE_BODY,
        on_click: Optional[Callable[[], None]] = None,
        *,
        normal_bg:    Optional[Tuple[int, int, int]] = None,
        hover_bg:     Optional[Tuple[int, int, int]] = None,
        pressed_bg:   Optional[Tuple[int, int, int]] = None,
        border_color: Optional[Tuple[int, int, int]] = None,
        text_color:   Optional[Tuple[int, int, int]] = None,
        border_width: int = 2,
        border_radius: int = 6,
    ) -> None:
        super().__init__(x, y, width, height)
        self._text = text
        self._font_size = font_size
        self._on_click = on_click

        # 颜色
        self._normal_bg   = normal_bg   or self._DEFAULT_NORMAL_BG
        self._hover_bg    = hover_bg    or self._DEFAULT_HOVER_BG
        self._pressed_bg  = pressed_bg  or self._DEFAULT_PRESSED_BG
        self._border_color = border_color or self._DEFAULT_BORDER
        self._text_color   = text_color  or self._DEFAULT_TEXT_COLOR
        self._border_width = border_width
        self._border_radius = border_radius

        # 状态
        self._is_hovered  = False
        self._is_pressed  = False

        # 字体（懒加载）
        self._font = None

    # ── 公开属性 ──────────────────────────────────────

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value

    def set_on_click(self, callback: Callable[[], None]) -> None:
        self._on_click = callback

    # ── 字体懒加载 ────────────────────────────────────

    def _get_font(self):
        if self._font is None and _pygame_available:
            self._font = pygame.font.SysFont("microsoftyahei,simhei,arial", self._font_size)
        return self._font

    # ── 事件处理 ──────────────────────────────────────

    def handle_event(self, event) -> bool:
        if not self._visible or not self._enabled:
            return False
        if not _pygame_available:
            return False

        if event.type == pygame.MOUSEMOTION:
            self._is_hovered = self.contains_point(*event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.contains_point(*event.pos):
                self._is_pressed = True
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_pressed = self._is_pressed
            self._is_pressed = False
            if was_pressed and self.contains_point(*event.pos):
                if self._on_click:
                    self._on_click()
                return True

        return super().handle_event(event)

    # ── 渲染 ──────────────────────────────────────────

    def render(self, surface) -> None:
        if not self._visible or not _pygame_available:
            return

        # 选取背景色
        if not self._enabled:
            bg = self._DEFAULT_DISABLED_BG
            text_color = self._DEFAULT_DISABLED_TEXT
            border = self._border_color
        elif self._is_pressed:
            bg = self._pressed_bg
            text_color = self._text_color
            border = self._DEFAULT_HOVER_BORDER
        elif self._is_hovered:
            bg = self._hover_bg
            text_color = self._text_color
            border = self._DEFAULT_HOVER_BORDER
        else:
            bg = self._normal_bg
            text_color = self._text_color
            border = self._border_color

        rect = pygame.Rect(self._x, self._y, self._width, self._height)

        # 绘制背景（圆角）
        pygame.draw.rect(surface, bg, rect, border_radius=self._border_radius)
        # 绘制边框
        if self._border_width > 0:
            pygame.draw.rect(
                surface, border, rect,
                width=self._border_width,
                border_radius=self._border_radius,
            )

        # 绘制文字
        if self._text:
            font = self._get_font()
            if font:
                # 按下时轻微向下偏移，模拟按压
                offset_y = 2 if self._is_pressed else 0
                text_surf = font.render(self._text, True, text_color)
                text_rect = text_surf.get_rect(
                    center=(
                        self._x + self._width // 2,
                        self._y + self._height // 2 + offset_y,
                    )
                )
                surface.blit(text_surf, text_rect)

        # 渲染子组件
        self._render_children(surface)
