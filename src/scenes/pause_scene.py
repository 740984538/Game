"""
暂停场景 - 对应开发计划 8-14，文档 §6.1.1 Layer 5

进入方式：
    self.game.state_machine.change(
        GameState.PAUSE,
        return_state=GameState.COMBAT,   # 或 MAP_NAVIGATION
        return_kwargs={...},             # 用于恢复返回场景的 enter() 参数
    )

完成标志（开发计划 8-14）：
  - 按 ESC 键弹出（由调用方场景触发）
  - 半透明遮罩
  - 菜单选项：继续游戏 / 设置 / 放弃当局回到主菜单
  - 点击"继续游戏"或再次按 ESC 返回上一个状态
  - 放弃当局时二次确认弹窗
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

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
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_DIVIDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_WHITE, COLOR_GOLD, COLOR_DANGER,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


# ── 布局 ────────────────────────────────────────────────────────────────────

_PANEL_W = 380
_PANEL_H = 460
_PANEL_X = (SCREEN_WIDTH - _PANEL_W) // 2
_PANEL_Y = (SCREEN_HEIGHT - _PANEL_H) // 2

_BTN_W = 280
_BTN_H = 48
_BTN_GAP = 14


class PauseScene(BaseScene):
    """
    暂停菜单场景。
    充当一层覆盖在原场景上的菜单。
    """

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._return_state: GameState = GameState.MAIN_MENU
        self._return_kwargs: dict = {}
        self._abandon_dialog: Optional[Dialog] = None
        self._built: bool = False

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def enter(self, **kwargs) -> None:
        self._return_state = kwargs.get("return_state", GameState.MAIN_MENU)
        self._return_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("return_state", "return_kwargs")
        }
        # 显式 return_kwargs 优先
        if "return_kwargs" in kwargs and isinstance(kwargs["return_kwargs"], dict):
            self._return_kwargs.update(kwargs["return_kwargs"])

        if not self._built:
            self._build_ui()
            self._built = True
        if self._abandon_dialog:
            self._abandon_dialog.hide()
        logger.info("进入暂停场景, 返回=%s", self._return_state)

    def exit(self) -> None:
        if self._abandon_dialog:
            self._abandon_dialog.hide()
        logger.info("离开暂停场景")

    # ── UI 构建 ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 中央面板
        panel = Panel(
            _PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_TEXT_PRIMARY,
            border_width=2,
            border_radius=10,
        )
        self._widgets.append(panel)

        # 标题
        title = Label(
            _PANEL_X, _PANEL_Y + 24, _PANEL_W, 40,
            text="游戏暂停",
            font_size=FONT_SIZE_H1,
            color=COLOR_TEXT_PRIMARY,
            align="center", bold=True,
        )
        self._widgets.append(title)

        # 副标题（提示）
        hint = Label(
            _PANEL_X, _PANEL_Y + 78, _PANEL_W, 24,
            text="按 ESC 继续游戏",
            font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self._widgets.append(hint)

        # 分割线
        divider = Panel(
            _PANEL_X + 60, _PANEL_Y + 116, _PANEL_W - 120, 2,
            bg_color=COLOR_DIVIDER, border_color=None, border_width=0,
        )
        self._widgets.append(divider)

        # 按钮列表
        btn_y = _PANEL_Y + 140
        btn_x = _PANEL_X + (_PANEL_W - _BTN_W) // 2

        items = [
            ("继续游戏", self._on_resume,
             {"normal_bg": (30, 70, 30), "hover_bg": (50, 110, 50),
              "border_color": (60, 180, 60)}),
            ("查看遗物 / 卡组", self._on_inventory, {}),
            ("设置", self._on_settings, {}),
            ("放弃当局", self._on_abandon,
             {"normal_bg": (70, 20, 20), "hover_bg": (120, 30, 30),
              "border_color": COLOR_DANGER}),
        ]

        for i, (label, cb, style) in enumerate(items):
            btn = Button(
                btn_x, btn_y + i * (_BTN_H + _BTN_GAP),
                _BTN_W, _BTN_H,
                text=label,
                font_size=FONT_SIZE_H3,
                on_click=cb,
                **style,
            )
            self._widgets.append(btn)

        # 放弃确认对话框
        self._abandon_dialog = Dialog(
            title="放弃当局",
            content="确定要放弃当前局并返回主菜单吗？\n本局进度将丢失。",
            confirm_text="确定放弃",
            cancel_text="取消",
            on_confirm=self._do_abandon,
            close_on_overlay=True,
        )

    # ── 按钮回调 ──────────────────────────────────────────────────────────

    def _on_resume(self) -> None:
        logger.info("继续游戏 -> %s", self._return_state)
        self.game.state_machine.change(self._return_state, **self._return_kwargs)

    def _on_inventory(self) -> None:
        # TODO: 打开遗物/卡组查看面板（阶段 9 图鉴）
        logger.info("查看遗物/卡组（占位）")

    def _on_settings(self) -> None:
        # 设置场景 enter 不需要 run 数据
        logger.info("打开设置")
        # 让设置场景知道 ESC 后该回到哪
        self.game.state_machine.change(
            GameState.SETTINGS,
            return_state=GameState.PAUSE,
            return_kwargs={
                "return_state": self._return_state,
                "return_kwargs": dict(self._return_kwargs),
            },
        )

    def _on_abandon(self) -> None:
        if self._abandon_dialog:
            self._abandon_dialog.show()

    def _do_abandon(self) -> None:
        logger.info("放弃当局")
        # 标记 RunState 结束，跳转到 GAME_OVER（统计可读）
        if hasattr(self.game, "run_state") and self.game.run_state:
            self.game.run_state.end_run()
            self.game.state_machine.change(
                GameState.GAME_OVER,
                reason="abandon",
            )
        else:
            self.game.state_machine.change(GameState.MAIN_MENU)

    # ── 事件 / 更新 / 渲染 ────────────────────────────────────────────────

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return

        # 对话框优先
        if self._abandon_dialog and self._abandon_dialog.visible:
            self._abandon_dialog.handle_event(event)
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_resume()
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

        # 半透明遮罩（不清屏，让"暂停时显示原场景"成为可能；
        # 但状态机切换后原场景已经退出，因此这里画一个深色背景作为替代）
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.fill(COLOR_BG_DARK)
        surface.blit(overlay, (0, 0))

        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)

        # 对话框最后渲染
        if self._abandon_dialog:
            self._abandon_dialog.render(surface)
