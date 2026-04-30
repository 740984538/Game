"""
主菜单场景
对应文档 §6.1，阶段2-7（UI）/ 阶段2-8（交互）
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.scenes.base_scene import BaseScene
from src.ui.widgets.button import Button
from src.ui.widgets.label import Label
from src.ui.widgets.panel import Panel
from src.ui.widgets.dialog import Dialog
from src.utils.constants import (
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_TEXT_PRIMARY,
    COLOR_WHITE, COLOR_DIVIDER, COLOR_GOLD,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY,
    SCREEN_WIDTH, SCREEN_HEIGHT,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)

# ── 布局常量 ──────────────────────────────────────────────────
_BTN_W   = 280
_BTN_H   = 52
_BTN_GAP = 16
_CENTER_X = SCREEN_WIDTH // 2


class MainMenuScene(BaseScene):
    """
    主菜单场景：
    - 显示游戏标题
    - 按钮：开始游戏 / 每日挑战 / 图鉴 / 设置 / 退出
    - 退出时弹出确认对话框
    """

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._exit_dialog: Dialog | None = None
        self._bg_surface = None
        self._built = False

    # ── 场景生命周期 ──────────────────────────────────

    def enter(self, **kwargs) -> None:
        if not self._built:
            self._build_ui()
            self._built = True
        logger.info("进入主菜单")

    def exit(self) -> None:
        logger.info("离开主菜单")

    # ── UI 构建 ────────────────────────────────────────

    def _build_ui(self) -> None:
        """构建主菜单所有 UI 元素"""
        # ── 背景面板 ──────────────────────────────────
        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK,
            border_color=None,
            border_width=0,
        )
        self._widgets.append(bg)

        # ── 装饰侧边条 ────────────────────────────────
        left_bar = Panel(
            0, 0, 6, SCREEN_HEIGHT,
            bg_color=COLOR_TEXT_PRIMARY,
            border_color=None,
            border_width=0,
        )
        right_bar = Panel(
            SCREEN_WIDTH - 6, 0, 6, SCREEN_HEIGHT,
            bg_color=COLOR_TEXT_PRIMARY,
            border_color=None,
            border_width=0,
        )
        self._widgets.extend([left_bar, right_bar])

        # ── 标题区域 ──────────────────────────────────
        title_label = Label(
            _CENTER_X - 350, 100, 700, 70,
            text="深渊回响：无尽轮回",
            font_size=FONT_SIZE_H1,
            color=COLOR_TEXT_PRIMARY,
            align="center",
            bold=True,
        )
        subtitle_label = Label(
            _CENTER_X - 250, 178, 500, 32,
            text="ECHOES OF THE ABYSS",
            font_size=FONT_SIZE_BODY,
            color=(140, 140, 180),
            align="center",
        )
        self._widgets.extend([title_label, subtitle_label])

        # ── 分割线 ────────────────────────────────────
        divider = Panel(
            _CENTER_X - 150, 220, 300, 2,
            bg_color=COLOR_DIVIDER,
            border_color=None,
            border_width=0,
        )
        self._widgets.append(divider)

        # ── 按钮列表 ──────────────────────────────────
        btn_start_y = 260
        buttons_config = [
            ("开始游戏",   self._on_start_game),
            ("每日挑战",   self._on_daily_challenge),
            ("图鉴",       self._on_codex),
            ("设置",       self._on_settings),
            ("退出游戏",   self._on_quit),
        ]

        for i, (text, cb) in enumerate(buttons_config):
            btn_y = btn_start_y + i * (_BTN_H + _BTN_GAP)
            btn_x = _CENTER_X - _BTN_W // 2
            btn = Button(
                btn_x, btn_y, _BTN_W, _BTN_H,
                text=text,
                font_size=FONT_SIZE_H3 if i == 0 else FONT_SIZE_BODY,
                on_click=cb,
            )
            self._widgets.append(btn)

        # ── 版本号 ────────────────────────────────────
        version_label = Label(
            SCREEN_WIDTH - 160, SCREEN_HEIGHT - 32,
            150, 24,
            text="v0.2.0-alpha",
            font_size=14,
            color=(80, 80, 100),
            align="right",
        )
        self._widgets.append(version_label)

        # ── 退出确认对话框 ────────────────────────────
        self._exit_dialog = Dialog(
            title="退出游戏",
            content="确定要退出游戏吗？",
            confirm_text="确定退出",
            cancel_text="取消",
            on_confirm=self._do_quit,
            on_cancel=None,
            close_on_overlay=True,
        )

    # ── 按钮回调 ──────────────────────────────────────

    def _on_start_game(self) -> None:
        logger.info("点击：开始游戏")
        self.game.state_machine.change(GameState.CHARACTER_SELECT)

    def _on_daily_challenge(self) -> None:
        logger.info("点击：每日挑战")
        self.game.state_machine.change(GameState.CHARACTER_SELECT, daily=True)

    def _on_codex(self) -> None:
        logger.info("点击：图鉴（暂未实现，占位）")
        # TODO: 切换到图鉴场景（阶段9-10实现）

    def _on_settings(self) -> None:
        logger.info("点击：设置")
        self.game.state_machine.change(GameState.SETTINGS)

    def _on_quit(self) -> None:
        if self._exit_dialog:
            self._exit_dialog.show()

    def _do_quit(self) -> None:
        logger.info("用户确认退出游戏")
        self.game.running = False

    # ── 事件 / 更新 / 渲染 ────────────────────────────

    def handle_event(self, event) -> None:
        # 对话框优先消费事件
        if self._exit_dialog and self._exit_dialog.visible:
            self._exit_dialog.handle_event(event)
            return
        for widget in self._widgets:
            if widget.handle_event(event):
                break

    def update(self, dt: float) -> None:
        for widget in self._widgets:
            widget.update(dt)

    def render(self, surface) -> None:
        if not _pygame_available:
            return

        # 清屏
        surface.fill(COLOR_BG_DARK)

        # 渲染所有 widget
        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)

        # 对话框最后渲染（在最顶层）
        if self._exit_dialog:
            self._exit_dialog.render(surface)
