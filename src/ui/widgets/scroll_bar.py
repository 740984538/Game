"""
滚动条组件
对应文档 §6.1 UI框架，阶段2-5
"""
from __future__ import annotations
from typing import Callable, Optional, Tuple

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.ui.widgets.base_widget import UIComponent
from src.utils.constants import COLOR_BG_DARK, COLOR_DIVIDER, COLOR_TEXT_SECONDARY


class ScrollBar(UIComponent):
    """
    滚动条组件，支持垂直和水平两种方向。

    content_size: 内容总长度（像素）
    view_size:    可视区域长度（像素），初始与 width/height 一致
    当 content_size <= view_size 时，滑块填满整个轨道，不可拖动。

    on_scroll(ratio): ratio 在 [0.0, 1.0] 之间，0 为起始端
    """

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        content_size: int = 0,
        view_size: Optional[int] = None,
        orientation: str = "vertical",   # "vertical" | "horizontal"
        on_scroll: Optional[Callable[[float], None]] = None,
        track_color: Tuple[int, int, int] = COLOR_BG_DARK,
        thumb_color: Tuple[int, int, int] = COLOR_TEXT_SECONDARY,
        thumb_hover_color: Tuple[int, int, int] = COLOR_DIVIDER,
        scroll_step: int = 20,           # 每次滚轮滚动的像素量
    ) -> None:
        super().__init__(x, y, width, height)
        self._orientation   = orientation
        self._content_size  = max(content_size, 1)
        self._view_size     = view_size or (height if orientation == "vertical" else width)
        self._on_scroll     = on_scroll
        self._track_color   = track_color
        self._thumb_color   = thumb_color
        self._thumb_hover_color = thumb_hover_color
        self._scroll_step   = scroll_step

        self._scroll_ratio: float = 0.0   # [0, 1]
        self._dragging: bool = False
        self._drag_start_pos: int = 0
        self._drag_start_ratio: float = 0.0
        self._is_thumb_hovered: bool = False

    # ── 属性 ──────────────────────────────────────────

    @property
    def scroll_ratio(self) -> float:
        return self._scroll_ratio

    @scroll_ratio.setter
    def scroll_ratio(self, value: float) -> None:
        self._scroll_ratio = max(0.0, min(1.0, value))

    @property
    def scroll_offset(self) -> int:
        """当前滚动偏移量（像素），供外部使用"""
        max_offset = max(0, self._content_size - self._view_size)
        return int(self._scroll_ratio * max_offset)

    def set_content_size(self, content_size: int) -> None:
        self._content_size = max(content_size, 1)
        # 重新夹紧比例
        self.scroll_ratio = self._scroll_ratio

    def set_view_size(self, view_size: int) -> None:
        self._view_size = max(view_size, 1)
        self.scroll_ratio = self._scroll_ratio

    # ── 辅助计算 ──────────────────────────────────────

    def _is_scrollable(self) -> bool:
        return self._content_size > self._view_size

    def _thumb_rect(self) -> Tuple[int, int, int, int]:
        """返回滑块的 (x, y, w, h)"""
        if self._orientation == "vertical":
            track_len = self._height
            ratio = min(self._view_size / self._content_size, 1.0)
            thumb_len = max(int(track_len * ratio), 20)
            max_offset = track_len - thumb_len
            thumb_pos = int(self._scroll_ratio * max_offset) if self._is_scrollable() else 0
            return (self._x, self._y + thumb_pos, self._width, thumb_len)
        else:
            track_len = self._width
            ratio = min(self._view_size / self._content_size, 1.0)
            thumb_len = max(int(track_len * ratio), 20)
            max_offset = track_len - thumb_len
            thumb_pos = int(self._scroll_ratio * max_offset) if self._is_scrollable() else 0
            return (self._x + thumb_pos, self._y, thumb_len, self._height)

    def _pos_to_ratio(self, pos: int) -> float:
        """将轨道上的绝对坐标转换为比例"""
        tx, ty, tw, th = self._thumb_rect()
        if self._orientation == "vertical":
            track_len = self._height
            thumb_len = th
        else:
            track_len = self._width
            thumb_len = tw
        usable = track_len - thumb_len
        if usable <= 0:
            return 0.0
        if self._orientation == "vertical":
            rel = pos - self._y - thumb_len // 2
        else:
            rel = pos - self._x - thumb_len // 2
        return max(0.0, min(1.0, rel / usable))

    # ── 事件处理 ──────────────────────────────────────

    def handle_event(self, event) -> bool:
        if not self._visible or not self._enabled or not _pygame_available:
            return False
        if not self._is_scrollable():
            return False

        tx, ty, tw, th = self._thumb_rect()
        thumb_rect = pygame.Rect(tx, ty, tw, th)

        if event.type == pygame.MOUSEMOTION:
            self._is_thumb_hovered = thumb_rect.collidepoint(event.pos)
            if self._dragging:
                if self._orientation == "vertical":
                    delta = event.pos[1] - self._drag_start_pos
                    track_len = self._height - th
                else:
                    delta = event.pos[0] - self._drag_start_pos
                    track_len = self._width - tw
                if track_len > 0:
                    new_ratio = self._drag_start_ratio + delta / track_len
                    self.scroll_ratio = new_ratio
                    if self._on_scroll:
                        self._on_scroll(self._scroll_ratio)
                return True

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if thumb_rect.collidepoint(event.pos):
                self._dragging = True
                if self._orientation == "vertical":
                    self._drag_start_pos = event.pos[1]
                else:
                    self._drag_start_pos = event.pos[0]
                self._drag_start_ratio = self._scroll_ratio
                return True
            # 点击轨道区域（非滑块）则跳转
            elif self.contains_point(*event.pos):
                self.scroll_ratio = self._pos_to_ratio(
                    event.pos[1] if self._orientation == "vertical" else event.pos[0]
                )
                if self._on_scroll:
                    self._on_scroll(self._scroll_ratio)
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False

        elif event.type == pygame.MOUSEWHEEL:
            # 仅在鼠标位于组件范围内时响应滚轮
            mouse_pos = pygame.mouse.get_pos()
            if self.contains_point(*mouse_pos):
                max_offset = max(0, self._content_size - self._view_size)
                if max_offset > 0:
                    step_ratio = self._scroll_step / max_offset
                    # event.y: 向上为正，向下为负
                    self.scroll_ratio -= event.y * step_ratio
                    if self._on_scroll:
                        self._on_scroll(self._scroll_ratio)
                    return True

        return False

    # ── 渲染 ──────────────────────────────────────────

    def render(self, surface) -> None:
        if not self._visible or not _pygame_available:
            return

        # 轨道背景
        track_rect = pygame.Rect(self._x, self._y, self._width, self._height)
        pygame.draw.rect(surface, self._track_color, track_rect, border_radius=4)

        # 滑块
        tx, ty, tw, th = self._thumb_rect()
        thumb_rect = pygame.Rect(tx, ty, tw, th)
        color = self._thumb_hover_color if (self._is_thumb_hovered or self._dragging) else self._thumb_color
        pygame.draw.rect(surface, color, thumb_rect, border_radius=4)

        self._render_children(surface)
