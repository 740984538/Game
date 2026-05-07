"""
角色卡片组件
对应开发计划 §3-6（角色卡片 UI）
显示角色头像（占位图）、名称、初始HP、核心机制简介、锁定状态。
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
    COLOR_BG_LIGHT, COLOR_DIVIDER, COLOR_TEXT_PRIMARY,
    COLOR_WHITE, COLOR_TEXT_SECONDARY, COLOR_GOLD,
    FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)

# 角色职业 → 占位图颜色
_ROLE_COLORS = {
    "warrior":  (100, 140, 180),
    "assassin": (160, 80, 120),
    "mage":     (120, 80, 200),
    "ranger":   (80, 160, 100),
    "summoner": (140, 120, 180),
}

# 卡片内部布局常量
_AVATAR_SIZE = 72
_PADDING = 12
_BORDER_RADIUS = 8


class CharacterCard(UIComponent):
    """
    角色选择界面的卡片组件。

    显示内容：
    - 角色头像（根据角色职业绘制彩色占位方块）
    - 角色名称
    - 初始 HP
    - 核心机制简介
    - 未解锁时显示锁定遮罩

    交互：
    - 点击触发 on_click 回调
    - 支持 selected / locked 两种视觉状态
    """

    # 颜色方案
    _NORMAL_BG = COLOR_BG_LIGHT
    _SELECTED_BG = (30, 50, 90)
    _SELECTED_BORDER = COLOR_TEXT_PRIMARY
    _NORMAL_BORDER = COLOR_DIVIDER
    _LOCKED_OVERLAY = (0, 0, 0, 160)

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        char_id: str = "",
        name: str = "",
        role: str = "",
        hp: int = 0,
        mechanic: str = "",
        unlock_cost: int = 0,
        locked: bool = False,
        on_click: Optional[Callable[["CharacterCard"], None]] = None,
    ) -> None:
        super().__init__(x, y, width, height)
        self.char_id = char_id
        self._name = name
        self._role = role
        self._hp = hp
        self._mechanic = mechanic
        self._unlock_cost = unlock_cost
        self._locked = locked
        self._on_click = on_click

        self._selected = False
        self._hovered = False

        # 字体懒加载
        self._font_name: Optional["pygame.font.Font"] = None
        self._font_body: Optional["pygame.font.Font"] = None
        self._font_caption: Optional["pygame.font.Font"] = None

    # ── 属性 ──────────────────────────────────────────

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value

    @property
    def locked(self) -> bool:
        return self._locked

    @locked.setter
    def locked(self, value: bool) -> None:
        self._locked = value

    # ── 字体懒加载 ────────────────────────────────────

    def _get_font_name(self):
        if self._font_name is None and _pygame_available:
            self._font_name = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_H3, bold=True
            )
        return self._font_name

    def _get_font_body(self):
        if self._font_body is None and _pygame_available:
            self._font_body = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_BODY
            )
        return self._font_body

    def _get_font_caption(self):
        if self._font_caption is None and _pygame_available:
            self._font_caption = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_CAPTION
            )
        return self._font_caption

    # ── 事件处理 ──────────────────────────────────────

    def handle_event(self, event) -> bool:
        if not self._visible or not self._enabled or not _pygame_available:
            return False

        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.contains_point(*event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.contains_point(*event.pos):
                if self._on_click:
                    self._on_click(self)
                return True

        return False

    # ── 渲染 ──────────────────────────────────────────

    def render(self, surface) -> None:
        if not self._visible or not _pygame_available:
            return

        rect = pygame.Rect(self._x, self._y, self._width, self._height)

        # ── 背景 ──
        bg = self._SELECTED_BG if self._selected else self._NORMAL_BG
        pygame.draw.rect(surface, bg, rect, border_radius=_BORDER_RADIUS)

        # ── 边框 ──
        border = self._SELECTED_BORDER if self._selected else self._NORMAL_BORDER
        border_w = 3 if self._selected else 1
        if self._hovered and not self._selected:
            border = COLOR_TEXT_PRIMARY
            border_w = 2
        pygame.draw.rect(
            surface, border, rect,
            width=border_w, border_radius=_BORDER_RADIUS,
        )

        # ── 头像占位图 ──
        avatar_x = self._x + _PADDING
        avatar_y = self._y + _PADDING
        avatar_rect = pygame.Rect(avatar_x, avatar_y, _AVATAR_SIZE, _AVATAR_SIZE)
        avatar_color = _ROLE_COLORS.get(self._role, (120, 120, 120))
        pygame.draw.rect(surface, avatar_color, avatar_rect, border_radius=6)
        # 在占位图中央画角色名首字
        font_name = self._get_font_name()
        if font_name and self._name:
            initial_surf = font_name.render(self._name[0], True, COLOR_WHITE)
            initial_rect = initial_surf.get_rect(center=avatar_rect.center)
            surface.blit(initial_surf, initial_rect)

        # ── 文本区域 ──
        text_x = avatar_x + _AVATAR_SIZE + _PADDING
        text_w = self._width - _AVATAR_SIZE - _PADDING * 3

        # 角色名称
        if font_name and self._name:
            name_surf = font_name.render(self._name, True, COLOR_WHITE)
            surface.blit(name_surf, (text_x, avatar_y))

        # HP 信息
        font_body = self._get_font_body()
        if font_body:
            hp_text = f"HP: {self._hp}"
            hp_surf = font_body.render(hp_text, True, (100, 200, 100))
            surface.blit(hp_surf, (text_x, avatar_y + 28))

        # 核心机制简介
        font_caption = self._get_font_caption()
        if font_caption and self._mechanic:
            # 简单截断，避免溢出
            mech_text = self._mechanic
            mech_surf = font_caption.render(mech_text, True, COLOR_TEXT_SECONDARY)
            # 裁剪到可用宽度
            if mech_surf.get_width() > text_w:
                mech_text = mech_text[:20] + "..."
                mech_surf = font_caption.render(mech_text, True, COLOR_TEXT_SECONDARY)
            surface.blit(mech_surf, (text_x, avatar_y + 52))

        # ── 锁定遮罩 ──
        if self._locked:
            overlay = pygame.Surface(
                (self._width, self._height), pygame.SRCALPHA
            )
            overlay.fill(self._LOCKED_OVERLAY)
            surface.blit(overlay, (self._x, self._y))

            # 锁定图标 + 解锁费用
            if font_body:
                lock_text = f"需要 {self._unlock_cost} 灵魂碎片解锁"
                lock_surf = font_body.render(lock_text, True, COLOR_GOLD)
                lock_rect = lock_surf.get_rect(
                    center=(self._x + self._width // 2, self._y + self._height // 2)
                )
                surface.blit(lock_surf, lock_rect)
