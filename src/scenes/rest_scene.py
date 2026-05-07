"""
休息点场景 - 对应开发计划 8-7，文档 §4.1.2

进入方式（由 MapNavigationScene 在节点为 REST 时切换）::

    self.game.state_machine.change(
        GameState.REST,
        floor=floor, floor_number=N, character_id=..., daily=..., seed=..., node_id=...,
    )

完成标志（开发计划 8-7）：
  - 显示两个选项：休息恢复 / 锻造升级
  - 选择休息：恢复 30% 最大 HP
  - 选择锻造：选择一张卡牌升级
  - 选择后返回地图
"""
from __future__ import annotations

import logging
from typing import List, Optional, TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.scenes.base_scene import BaseScene
from src.ui.widgets.button import Button
from src.ui.widgets.label import Label
from src.ui.widgets.panel import Panel
from src.utils.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_DIVIDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_WHITE, COLOR_GOLD, COLOR_HEAL,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


# ── 配置 ────────────────────────────────────────────────────────────────────

# 休息恢复 HP 比例
REST_HEAL_PERCENT: float = 0.30

# 布局
_OPTION_W = 360
_OPTION_H = 300
_OPTION_GAP = 40
_CENTER_X = SCREEN_WIDTH // 2
_CENTER_Y = SCREEN_HEIGHT // 2

# 升级面板（卡牌选择）
_UPGRADE_PANEL_W = 800
_UPGRADE_PANEL_H = 500


class RestScene(BaseScene):
    """
    休息点：恢复 HP 或 升级一张卡牌（二选一）。
    完成后返回地图。
    """

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._upgrade_widgets: list = []
        self._return_kwargs: dict = {}
        self._show_upgrade_panel: bool = False
        self._info_label: Optional[Label] = None

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def enter(self, **kwargs) -> None:
        # 保留所有上下文以便返回时传回 MAP_NAVIGATION
        self._return_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("room_type", "node_id")
        }
        # 保留 floor 信息
        self._show_upgrade_panel = False
        self._widgets.clear()
        self._upgrade_widgets.clear()
        self._build_ui()
        logger.info("进入休息场景")

    def exit(self) -> None:
        self._widgets.clear()
        self._upgrade_widgets.clear()
        logger.info("离开休息场景")

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 背景
        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK,
            border_color=None, border_width=0,
        )
        self._widgets.append(bg)

        # 标题
        title = Label(
            _CENTER_X - 300, 60, 600, 50,
            text="休 息 点",
            font_size=FONT_SIZE_H1,
            color=COLOR_TEXT_PRIMARY,
            align="center", bold=True,
        )
        self._widgets.append(title)

        subtitle = Label(
            _CENTER_X - 400, 116, 800, 26,
            text="温暖的篝火在此等待。在前往下一房间前，你可以做一件事。",
            font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self._widgets.append(subtitle)

        # 显示玩家当前 HP / 卡组数量
        rs = getattr(self.game, "run_state", None)
        if rs:
            heal_amount = max(1, int(rs.max_health * REST_HEAL_PERCENT))
            preview = (
                f"当前 HP：{rs.health}/{rs.max_health}    "
                f"卡组：{len(rs.deck)} 张"
            )
        else:
            heal_amount = 0
            preview = "（无玩家状态信息）"

        info = Label(
            _CENTER_X - 400, 154, 800, 24,
            text=preview,
            font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self._widgets.append(info)

        # 两个选项面板
        opt_y = 220
        opt_x_left = _CENTER_X - _OPTION_W - _OPTION_GAP // 2
        opt_x_right = _CENTER_X + _OPTION_GAP // 2

        # 休息选项
        rest_panel = Panel(
            opt_x_left, opt_y, _OPTION_W, _OPTION_H,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_HEAL,
            border_width=2,
            border_radius=10,
        )
        self._widgets.append(rest_panel)

        rest_title = Label(
            opt_x_left, opt_y + 20, _OPTION_W, 36,
            text="◆ 休息恢复",
            font_size=FONT_SIZE_H2,
            color=COLOR_HEAL,
            align="center", bold=True,
        )
        self._widgets.append(rest_title)

        rest_desc = Label(
            opt_x_left + 20, opt_y + 70, _OPTION_W - 40, 100,
            text=f"恢复 {int(REST_HEAL_PERCENT*100)}% 最大生命值\n（约 {heal_amount} HP）",
            font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE,
            align="center", wrap=True,
        )
        self._widgets.append(rest_desc)

        rest_btn = Button(
            opt_x_left + (_OPTION_W - 200) // 2, opt_y + _OPTION_H - 64,
            200, 44,
            text="选择休息",
            font_size=FONT_SIZE_H3,
            on_click=self._on_rest,
            normal_bg=(20, 60, 30),
            hover_bg=(30, 100, 50),
            border_color=COLOR_HEAL,
        )
        self._widgets.append(rest_btn)

        # 锻造选项
        forge_panel = Panel(
            opt_x_right, opt_y, _OPTION_W, _OPTION_H,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_GOLD,
            border_width=2,
            border_radius=10,
        )
        self._widgets.append(forge_panel)

        forge_title = Label(
            opt_x_right, opt_y + 20, _OPTION_W, 36,
            text="◆ 锻造升级",
            font_size=FONT_SIZE_H2,
            color=COLOR_GOLD,
            align="center", bold=True,
        )
        self._widgets.append(forge_title)

        # 锻造描述
        deck_count = len(rs.deck) if rs else 0
        forge_desc = Label(
            opt_x_right + 20, opt_y + 70, _OPTION_W - 40, 100,
            text=f"选择卡组中的一张卡牌升级\n（当前可升级：{deck_count} 张）",
            font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE,
            align="center", wrap=True,
        )
        self._widgets.append(forge_desc)

        forge_btn = Button(
            opt_x_right + (_OPTION_W - 200) // 2, opt_y + _OPTION_H - 64,
            200, 44,
            text="选择锻造",
            font_size=FONT_SIZE_H3,
            on_click=self._on_forge,
            normal_bg=(60, 50, 20),
            hover_bg=(100, 80, 30),
            border_color=COLOR_GOLD,
        )
        forge_btn.enabled = deck_count > 0
        self._widgets.append(forge_btn)

        # 跳过按钮
        skip_btn = Button(
            _CENTER_X - 100, SCREEN_HEIGHT - 80, 200, 44,
            text="跳过（直接离开）",
            font_size=FONT_SIZE_BODY,
            on_click=self._on_skip,
        )
        self._widgets.append(skip_btn)

        # 信息标签
        self._info_label = Label(
            0, SCREEN_HEIGHT - 32, SCREEN_WIDTH, 22,
            text="",
            font_size=FONT_SIZE_CAPTION,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self._widgets.append(self._info_label)

    # ── 操作 ──────────────────────────────────────────────────────────────

    def _on_rest(self) -> None:
        rs = getattr(self.game, "run_state", None)
        if rs is None:
            self._return_to_map()
            return
        heal_amount = max(1, int(rs.max_health * REST_HEAL_PERCENT))
        actual = rs.heal(heal_amount)
        logger.info("休息: 恢复 %d HP", actual)
        if self._info_label:
            self._info_label.text = f"恢复了 {actual} 点生命值"
        self._return_to_map()

    def _on_forge(self) -> None:
        """打开升级面板，列出可升级卡牌"""
        rs = getattr(self.game, "run_state", None)
        if rs is None or not rs.deck:
            self._return_to_map()
            return
        self._show_upgrade_panel = True
        self._build_upgrade_panel(rs.deck)

    def _on_skip(self) -> None:
        logger.info("跳过休息")
        self._return_to_map()

    def _build_upgrade_panel(self, deck_ids: List[str]) -> None:
        """构建卡牌选择面板"""
        # 加载卡牌配置以显示名称
        try:
            from src.data.config_loader import ConfigLoader
            all_cards = ConfigLoader().load_all_cards()
        except Exception:
            all_cards = {}

        # 半透明遮罩
        overlay = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=(0, 0, 0), bg_alpha=160,
            border_color=None, border_width=0,
        )
        self._upgrade_widgets.append(overlay)

        # 中央面板
        px = (SCREEN_WIDTH - _UPGRADE_PANEL_W) // 2
        py = (SCREEN_HEIGHT - _UPGRADE_PANEL_H) // 2
        panel = Panel(
            px, py, _UPGRADE_PANEL_W, _UPGRADE_PANEL_H,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_GOLD,
            border_width=2,
            border_radius=10,
        )
        self._upgrade_widgets.append(panel)

        title = Label(
            px, py + 16, _UPGRADE_PANEL_W, 36,
            text="选择一张卡牌升级",
            font_size=FONT_SIZE_H2,
            color=COLOR_GOLD,
            align="center", bold=True,
        )
        self._upgrade_widgets.append(title)

        # 卡牌网格
        cards_per_row = 4
        card_w = 160
        card_h = 90
        gap = 10
        grid_w = cards_per_row * card_w + (cards_per_row - 1) * gap
        start_x = px + (_UPGRADE_PANEL_W - grid_w) // 2
        start_y = py + 70

        for i, card_id in enumerate(deck_ids[:16]):  # 最多展示 16 张
            col = i % cards_per_row
            row = i // cards_per_row
            cx = start_x + col * (card_w + gap)
            cy = start_y + row * (card_h + gap)

            card_cfg = all_cards.get(card_id, {})
            card_name = card_cfg.get("name", card_id)
            card_cost = card_cfg.get("cost", 1)
            card_type = card_cfg.get("type", "skill")
            type_color_map = {
                "attack": (180, 60, 60),
                "skill":  (60, 120, 200),
                "ability": (160, 80, 200),
                "cursed": (40, 40, 40),
            }
            border_color = type_color_map.get(card_type, COLOR_DIVIDER)

            label_text = f"{card_name}\n费用 {card_cost}"
            btn = Button(
                cx, cy, card_w, card_h,
                text=label_text,
                font_size=FONT_SIZE_CAPTION,
                on_click=self._make_upgrade_handler(card_id),
                border_color=border_color,
            )
            self._upgrade_widgets.append(btn)

        # 取消按钮
        cancel_btn = Button(
            px + _UPGRADE_PANEL_W - 140 - 20,
            py + _UPGRADE_PANEL_H - 60,
            140, 40,
            text="取消",
            font_size=FONT_SIZE_H3,
            on_click=self._cancel_upgrade,
        )
        self._upgrade_widgets.append(cancel_btn)

    def _make_upgrade_handler(self, card_id: str):
        def _handler():
            rs = getattr(self.game, "run_state", None)
            if rs is None:
                self._return_to_map()
                return
            # 简单实现：将 card_id 替换为 card_id+ 作为升级标记
            upgraded_id = card_id if card_id.endswith("+") else f"{card_id}+"
            try:
                idx = rs.deck.index(card_id)
                rs.deck[idx] = upgraded_id
                logger.info("升级卡牌: %s -> %s", card_id, upgraded_id)
            except ValueError:
                pass
            self._return_to_map()
        return _handler

    def _cancel_upgrade(self) -> None:
        self._show_upgrade_panel = False
        self._upgrade_widgets.clear()

    # ── 返回地图 ──────────────────────────────────────────────────────────

    def _return_to_map(self) -> None:
        self.game.state_machine.change(GameState.MAP_NAVIGATION, **self._return_kwargs)

    # ── 事件 / 更新 / 渲染 ────────────────────────────────────────────────

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return

        if self._show_upgrade_panel:
            for widget in reversed(self._upgrade_widgets):
                if widget.handle_event(event):
                    return
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._return_to_map()
            return

        for widget in self._widgets:
            if widget.handle_event(event):
                break

    def update(self, dt: float) -> None:
        for widget in self._widgets:
            widget.update(dt)
        for widget in self._upgrade_widgets:
            widget.update(dt)

    def render(self, surface) -> None:
        if not _pygame_available:
            return
        surface.fill(COLOR_BG_DARK)
        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)
        if self._show_upgrade_panel:
            for widget in self._upgrade_widgets:
                if widget.visible:
                    widget.render(surface)
