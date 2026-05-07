"""
卡牌 UI 组件 - 对应开发计划 6-3
实现卡牌渲染：费用、名称、描述、边框颜色区分类型。

卡牌显示为矩形卡片:
  - 左上角显示费用
  - 中间显示名称
  - 下方显示描述
  - 不同类型不同边框颜色
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple, TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.utils.enums import CardType
from src.utils.constants import (
    COLOR_WHITE, COLOR_BLACK, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_H3,
)

if TYPE_CHECKING:
    from src.entities.cards.card import Card


# 卡牌类型对应的边框颜色
CARD_TYPE_COLORS = {
    CardType.ATTACK: (220, 60, 60),      # 红色 - 攻击
    CardType.SKILL: (60, 160, 220),      # 蓝色 - 技能
    CardType.ABILITY: (220, 180, 40),    # 金色 - 能力
    CardType.CURSED: (140, 40, 180),     # 紫色 - 诅咒
}

# 卡牌尺寸
CARD_WIDTH = 120
CARD_HEIGHT = 170
CARD_WIDTH_HOVER = 140
CARD_HEIGHT_HOVER = 195


class CardWidget:
    """
    卡牌 UI 渲染组件。

    功能:
    - 矩形卡片渲染
    - 左上角费用圆
    - 中间名称
    - 下方描述
    - 不同类型不同边框颜色
    - 鼠标悬停时放大
    - 选中高亮
    """

    def __init__(self, card: "Card", x: float = 0, y: float = 0,
                 on_click: Optional[Callable] = None) -> None:
        self.card = card
        self.x = x
        self.y = y
        self.on_click = on_click

        # 状态
        self.hovered = False
        self.selected = False
        self.visible = True
        self.dragging = False
        self.drag_offset_y = 0  # 拖拽偏移

        # 缓存字体
        self._font_cost = None
        self._font_name = None
        self._font_desc = None

    # ─── 属性 ─────────────────────────────────────────────────────────────

    @property
    def width(self) -> int:
        return CARD_WIDTH_HOVER if self.hovered else CARD_WIDTH

    @property
    def height(self) -> int:
        return CARD_HEIGHT_HOVER if self.hovered else CARD_HEIGHT

    @property
    def rect(self) -> "pygame.Rect":
        """当前卡牌矩形"""
        if not _pygame_available:
            return None
        w, h = self.width, self.height
        # 悬停时向上偏移
        offset_y = -25 if self.hovered else 0
        return pygame.Rect(
            int(self.x - w // 2),
            int(self.y - h + offset_y + self.drag_offset_y),
            w, h
        )

    # ─── 字体懒加载 ──────────────────────────────────────────────────────

    def _get_font_cost(self):
        if self._font_cost is None and _pygame_available:
            self._font_cost = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_H3, bold=True
            )
        return self._font_cost

    def _get_font_name(self):
        if self._font_name is None and _pygame_available:
            self._font_name = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_BODY, bold=True
            )
        return self._font_name

    def _get_font_desc(self):
        if self._font_desc is None and _pygame_available:
            self._font_desc = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_CAPTION
            )
        return self._font_desc

    # ─── 事件处理 ─────────────────────────────────────────────────────────

    def handle_event(self, event) -> bool:
        """处理鼠标事件，返回 True 表示事件被消费"""
        if not _pygame_available or not self.visible:
            return False

        if event.type == pygame.MOUSEMOTION:
            rect = self.rect
            if rect and rect.collidepoint(event.pos):
                self.hovered = True
            else:
                self.hovered = False
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            rect = self.rect
            if rect and rect.collidepoint(event.pos):
                if self.on_click:
                    self.on_click(self.card)
                return True

        return False

    def update(self, dt: float) -> None:
        """更新状态"""
        pass

    # ─── 渲染 ─────────────────────────────────────────────────────────────

    def render(self, surface) -> None:
        """渲染卡牌"""
        if not _pygame_available or not self.visible:
            return

        rect = self.rect
        if not rect:
            return

        # 边框颜色
        border_color = CARD_TYPE_COLORS.get(
            self.card.card_type, (120, 120, 120)
        )

        # 背景
        bg_color = (25, 25, 40) if not self.selected else (40, 40, 60)
        pygame.draw.rect(surface, bg_color, rect, border_radius=8)

        # 选中发光效果
        if self.selected:
            glow_rect = rect.inflate(4, 4)
            pygame.draw.rect(surface, (255, 220, 80), glow_rect, 3, border_radius=10)

        # 边框
        border_w = 3 if self.hovered else 2
        pygame.draw.rect(surface, border_color, rect, border_w, border_radius=8)

        # 费用圆 (左上角)
        cost_x = rect.left + 18
        cost_y = rect.top + 18
        cost_radius = 14
        pygame.draw.circle(surface, (30, 50, 80), (cost_x, cost_y), cost_radius)
        pygame.draw.circle(surface, (80, 160, 240), (cost_x, cost_y), cost_radius, 2)

        font_cost = self._get_font_cost()
        if font_cost:
            cost_text = str(self.card.cost)
            cost_surf = font_cost.render(cost_text, True, COLOR_WHITE)
            cost_rect = cost_surf.get_rect(center=(cost_x, cost_y))
            surface.blit(cost_surf, cost_rect)

        # 卡牌类型色带 (顶部)
        type_bar = pygame.Rect(rect.left + 2, rect.top + 2, rect.width - 4, 4)
        pygame.draw.rect(surface, border_color, type_bar)

        # 名称 (中上部)
        font_name = self._get_font_name()
        if font_name:
            name_text = self.card.display_name
            name_surf = font_name.render(name_text, True, COLOR_WHITE)
            name_rect = name_surf.get_rect(
                centerx=rect.centerx, top=rect.top + 40
            )
            surface.blit(name_surf, name_rect)

        # 分隔线
        sep_y = rect.top + 65
        pygame.draw.line(
            surface, (60, 60, 80),
            (rect.left + 10, sep_y), (rect.right - 10, sep_y), 1
        )

        # 描述 (下方，自动换行)
        font_desc = self._get_font_desc()
        if font_desc:
            desc_text = self.card.display_description
            self._render_wrapped_text(
                surface, font_desc, desc_text,
                rect.left + 8, sep_y + 8,
                rect.width - 16, (180, 180, 200)
            )

        # 升级标记
        if self.card.upgraded:
            up_font = self._get_font_cost()
            if up_font:
                up_surf = up_font.render("★", True, (255, 220, 80))
                up_rect = up_surf.get_rect(right=rect.right - 8, top=rect.top + 8)
                surface.blit(up_surf, up_rect)

    def _render_wrapped_text(self, surface, font, text: str,
                             x: int, y: int, max_width: int,
                             color: Tuple[int, int, int]) -> None:
        """简单的文字自动换行渲染"""
        words = list(text)  # 中文逐字处理
        line = ""
        line_y = y
        line_height = font.get_linesize()

        for char in words:
            test_line = line + char
            test_w, _ = font.size(test_line)
            if test_w > max_width and line:
                line_surf = font.render(line, True, color)
                surface.blit(line_surf, (x, line_y))
                line_y += line_height
                line = char
            else:
                line = test_line

        if line:
            line_surf = font.render(line, True, color)
            surface.blit(line_surf, (x, line_y))
