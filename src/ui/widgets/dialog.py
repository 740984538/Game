"""
模态对话框组件
对应文档 §6.1.1 界面层级，阶段2-6
"""
from __future__ import annotations
from typing import Callable, Optional, Tuple

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.ui.widgets.base_widget import UIComponent
from src.ui.widgets.panel import Panel
from src.ui.widgets.label import Label
from src.ui.widgets.button import Button
from src.utils.constants import (
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_DIVIDER,
    COLOR_TEXT_PRIMARY, COLOR_WHITE, COLOR_BLACK,
    FONT_SIZE_H3, FONT_SIZE_BODY,
    SCREEN_WIDTH, SCREEN_HEIGHT,
)


class Dialog(UIComponent):
    """
    模态对话框，显示在画面中央，带半透明遮罩背景。

    特性：
    - 遮罩阻止底层交互
    - 显示标题 + 内容文本
    - 最多两个按钮（确认 / 取消），均可自定义标签和回调
    - close_on_overlay=True 时，点击遮罩也可关闭对话框
    """

    _OVERLAY_COLOR = (0, 0, 0)
    _OVERLAY_ALPHA = 160

    def __init__(
        self,
        title: str = "提示",
        content: str = "",
        confirm_text: str = "确认",
        cancel_text: Optional[str] = "取消",   # None 表示不显示取消按钮
        on_confirm: Optional[Callable[[], None]] = None,
        on_cancel:  Optional[Callable[[], None]] = None,
        close_on_overlay: bool = True,
        dialog_width: int = 400,
        dialog_height: int = 220,
        screen_width: int = SCREEN_WIDTH,
        screen_height: int = SCREEN_HEIGHT,
    ) -> None:
        # Dialog 本身占满全屏（充当遮罩）
        super().__init__(0, 0, screen_width, screen_height)
        self._close_on_overlay = close_on_overlay
        self._visible = False  # 默认隐藏，调用 show() 打开

        # 对话框面板居中
        dlg_x = (screen_width  - dialog_width)  // 2
        dlg_y = (screen_height - dialog_height) // 2

        self._panel = Panel(
            dlg_x, dlg_y, dialog_width, dialog_height,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_DIVIDER,
            border_width=2,
            border_radius=8,
        )

        # 标题
        self._title_label = Label(
            dlg_x + 20, dlg_y + 16,
            dialog_width - 40, 36,
            text=title,
            font_size=FONT_SIZE_H3,
            color=COLOR_TEXT_PRIMARY,
            align="center",
            bold=True,
        )

        # 分割线 y
        divider_y = dlg_y + 58

        # 内容
        content_h = dialog_height - 58 - 60  # 留给按钮区60px
        self._content_label = Label(
            dlg_x + 20, divider_y + 8,
            dialog_width - 40, content_h,
            text=content,
            font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE,
            align="center",
            wrap=True,
        )

        # 按钮行
        btn_y = dlg_y + dialog_height - 52
        btn_h = 38
        has_cancel = cancel_text is not None
        if has_cancel:
            btn_w = (dialog_width - 60) // 2
            confirm_x = dlg_x + 20
            cancel_x  = dlg_x + 20 + btn_w + 20
        else:
            btn_w = dialog_width - 80
            confirm_x = dlg_x + 40

        self._confirm_btn = Button(
            confirm_x, btn_y, btn_w, btn_h,
            text=confirm_text,
            on_click=self._on_confirm_click,
            normal_bg=(70, 20, 20),
            hover_bg=(120, 30, 30),
            border_color=COLOR_TEXT_PRIMARY,
        )

        self._cancel_btn: Optional[Button] = None
        if has_cancel:
            self._cancel_btn = Button(
                cancel_x, btn_y, btn_w, btn_h,
                text=cancel_text,
                on_click=self._on_cancel_click,
            )

        self._on_confirm_cb = on_confirm
        self._on_cancel_cb  = on_cancel

        # 分割线位置存储（供 render 使用）
        self._divider_y   = divider_y
        self._dialog_rect = (dlg_x, dlg_y, dialog_width, dialog_height)

    # ── 回调内部处理 ──────────────────────────────────

    def _on_confirm_click(self) -> None:
        self.hide()
        if self._on_confirm_cb:
            self._on_confirm_cb()

    def _on_cancel_click(self) -> None:
        self.hide()
        if self._on_cancel_cb:
            self._on_cancel_cb()

    # ── 公开方法 ──────────────────────────────────────

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False

    def set_title(self, title: str) -> None:
        self._title_label.text = title

    def set_content(self, content: str) -> None:
        self._content_label.text = content

    # ── 事件处理 ──────────────────────────────────────

    def handle_event(self, event) -> bool:
        if not self._visible or not _pygame_available:
            return False

        # 先让按钮处理
        if self._confirm_btn.handle_event(event):
            return True
        if self._cancel_btn and self._cancel_btn.handle_event(event):
            return True

        # 点击遮罩关闭
        if self._close_on_overlay and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            dlg_x, dlg_y, dlg_w, dlg_h = self._dialog_rect
            dlg_rect = pygame.Rect(dlg_x, dlg_y, dlg_w, dlg_h)
            if not dlg_rect.collidepoint(event.pos):
                self._on_cancel_click()
                return True

        # 对话框可见时，消费所有事件，阻止底层响应
        return True

    # ── 渲染 ──────────────────────────────────────────

    def render(self, surface) -> None:
        if not self._visible or not _pygame_available:
            return

        # 半透明遮罩
        overlay = pygame.Surface((self._width, self._height), pygame.SRCALPHA)
        overlay.fill((*self._OVERLAY_COLOR, self._OVERLAY_ALPHA))
        surface.blit(overlay, (0, 0))

        # 面板
        self._panel.render(surface)

        # 标题
        self._title_label.render(surface)

        # 分割线
        dlg_x, dlg_y, dlg_w, _ = self._dialog_rect
        pygame.draw.line(
            surface, COLOR_DIVIDER,
            (dlg_x + 16, self._divider_y),
            (dlg_x + dlg_w - 16, self._divider_y),
            1,
        )

        # 内容
        self._content_label.render(surface)

        # 按钮
        self._confirm_btn.render(surface)
        if self._cancel_btn:
            self._cancel_btn.render(surface)
