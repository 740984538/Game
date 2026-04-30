"""
面板容器组件
对应文档 §6.1.1 界面层级，阶段2-4
"""
from __future__ import annotations
from typing import Optional, Tuple

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.ui.widgets.base_widget import UIComponent
from src.utils.constants import COLOR_BG_DARK, COLOR_DIVIDER


class Panel(UIComponent):
    """
    面板容器，支持：
    - 背景色填充（支持透明度）
    - 可选边框
    - 子组件管理（子组件使用绝对坐标，添加时不自动偏移）
    - 裁剪模式：clip=True 时只渲染面板范围内的内容
    """

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        bg_color: Optional[Tuple[int, int, int]] = COLOR_BG_DARK,
        bg_alpha: int = 255,            # 0-255，255 完全不透明
        border_color: Optional[Tuple[int, int, int]] = COLOR_DIVIDER,
        border_width: int = 1,
        border_radius: int = 4,
        clip: bool = False,
    ) -> None:
        super().__init__(x, y, width, height)
        self._bg_color    = bg_color
        self._bg_alpha    = bg_alpha
        self._border_color = border_color
        self._border_width = border_width
        self._border_radius = border_radius
        self._clip = clip

    # ── 属性 ──────────────────────────────────────────

    @property
    def bg_color(self) -> Optional[Tuple[int, int, int]]:
        return self._bg_color

    @bg_color.setter
    def bg_color(self, value: Optional[Tuple[int, int, int]]) -> None:
        self._bg_color = value

    @property
    def border_color(self) -> Optional[Tuple[int, int, int]]:
        return self._border_color

    @border_color.setter
    def border_color(self, value: Optional[Tuple[int, int, int]]) -> None:
        self._border_color = value

    @property
    def border_width(self) -> int:
        return self._border_width

    @border_width.setter
    def border_width(self, value: int) -> None:
        self._border_width = value

    # ── 渲染 ──────────────────────────────────────────

    def render(self, surface) -> None:
        if not self._visible or not _pygame_available:
            return

        rect = pygame.Rect(self._x, self._y, self._width, self._height)

        # 透明背景处理
        if self._bg_color is not None:
            if self._bg_alpha < 255:
                # 使用临时 surface 实现半透明
                bg_surf = pygame.Surface((self._width, self._height), pygame.SRCALPHA)
                r, g, b = self._bg_color
                bg_surf.fill((r, g, b, self._bg_alpha))
                surface.blit(bg_surf, (self._x, self._y))
            else:
                pygame.draw.rect(
                    surface, self._bg_color, rect,
                    border_radius=self._border_radius,
                )

        # 边框
        if self._border_color is not None and self._border_width > 0:
            pygame.draw.rect(
                surface, self._border_color, rect,
                width=self._border_width,
                border_radius=self._border_radius,
            )

        # 子组件渲染（可选裁剪）
        if self._clip and _pygame_available:
            old_clip = surface.get_clip()
            surface.set_clip(rect)
            self._render_children(surface)
            surface.set_clip(old_clip)
        else:
            self._render_children(surface)
