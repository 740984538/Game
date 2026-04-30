"""
文本标签组件
对应文档 §6.3.2 字体规范，阶段2-3
"""
from __future__ import annotations
from typing import Optional, Tuple

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.ui.widgets.base_widget import UIComponent
from src.utils.constants import COLOR_WHITE, FONT_SIZE_BODY


class Label(UIComponent):
    """
    文本标签组件，支持：
    - 不同字体大小
    - 自定义颜色
    - 左/中/右对齐（align: 'left' | 'center' | 'right'）
    - 自动换行（wrap=True 时按 width 折行）
    """

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str = "",
        font_size: int = FONT_SIZE_BODY,
        color: Tuple[int, int, int] = COLOR_WHITE,
        align: str = "left",   # 'left' | 'center' | 'right'
        wrap: bool = False,
        bold: bool = False,
        italic: bool = False,
    ) -> None:
        super().__init__(x, y, width, height)
        self._text = text
        self._font_size = font_size
        self._color = color
        self._align = align
        self._wrap = wrap
        self._bold = bold
        self._italic = italic
        self._font = None

    # ── 属性 ──────────────────────────────────────────

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value

    @property
    def color(self) -> Tuple[int, int, int]:
        return self._color

    @color.setter
    def color(self, value: Tuple[int, int, int]) -> None:
        self._color = value

    @property
    def align(self) -> str:
        return self._align

    @align.setter
    def align(self, value: str) -> None:
        assert value in ("left", "center", "right"), "align 必须是 left/center/right"
        self._align = value

    # ── 字体懒加载 ────────────────────────────────────

    def _get_font(self):
        if self._font is None and _pygame_available:
            self._font = pygame.font.SysFont(
                "microsoftyahei,simhei,arial",
                self._font_size,
                bold=self._bold,
                italic=self._italic,
            )
        return self._font

    # ── 换行辅助 ─────────────────────────────────────

    def _wrap_text(self, font, text: str, max_width: int):
        """将文本按 max_width 折行，返回行列表"""
        lines = []
        for paragraph in text.split("\n"):
            words = list(paragraph)  # 中文逐字分割
            if not words:
                lines.append("")
                continue
            current_line = ""
            for char in words:
                test_line = current_line + char
                if font.size(test_line)[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = char
            if current_line:
                lines.append(current_line)
        return lines

    # ── 渲染 ──────────────────────────────────────────

    def render(self, surface) -> None:
        if not self._visible or not self._text or not _pygame_available:
            return

        font = self._get_font()
        if not font:
            return

        if self._wrap:
            lines = self._wrap_text(font, self._text, self._width)
        else:
            lines = self._text.split("\n")

        line_height = font.get_linesize()
        total_height = line_height * len(lines)
        # 垂直居中起始 y
        start_y = self._y + (self._height - total_height) // 2

        for i, line in enumerate(lines):
            text_surf = font.render(line, True, self._color)
            line_y = start_y + i * line_height

            if self._align == "center":
                line_x = self._x + (self._width - text_surf.get_width()) // 2
            elif self._align == "right":
                line_x = self._x + self._width - text_surf.get_width()
            else:  # left
                line_x = self._x

            surface.blit(text_surf, (line_x, line_y))

        self._render_children(surface)
