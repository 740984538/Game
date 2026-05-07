"""
图鉴场景 - 阶段 9-10

分两个标签页：
  - 遗物图鉴：扫描 ``RelicRegistry`` 的所有遗物，已收集的展示完整信息
                未收集的显示 "???"
  - 卡牌图鉴：扫描 ``ConfigLoader.load_all_cards()`` 的所有卡牌

「已见过」记录在 ``MetaProgress.seen_relics / seen_cards`` 中。
本场景仅做查询，不修改元进度。
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple, TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.scenes.base_scene import BaseScene
from src.ui.widgets.button import Button
from src.ui.widgets.label import Label
from src.ui.widgets.panel import Panel
from src.entities.relics.relic import RelicRegistry
from src.data.config_loader import ConfigLoader
from src.utils.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_DIVIDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_WHITE, COLOR_GOLD, COLOR_EPIC,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RARITY_COLORS,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


_PANEL_W = 1100
_PANEL_H = 600
_PANEL_X = (SCREEN_WIDTH - _PANEL_W) // 2
_PANEL_Y = (SCREEN_HEIGHT - _PANEL_H) // 2

_TAB_RELICS = "relics"
_TAB_CARDS = "cards"

# 内容区行配置
_ITEM_ROW_H = 56
_ITEMS_PER_PAGE = 7


class CodexScene(BaseScene):
    """图鉴场景：展示已收集的遗物 / 卡牌"""

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._tab: str = _TAB_RELICS
        self._page: int = 0
        # 缓存
        self._relics_data: List[Tuple[str, str, str, str]] = []   # (id, name, rarity, desc)
        self._cards_data:  List[Tuple[str, str, str, str]] = []   # (id, name, rarity, desc)
        # 动态控件
        self._tab_btn_relics: Optional[Button] = None
        self._tab_btn_cards:  Optional[Button] = None
        self._page_label:     Optional[Label] = None
        self._progress_label: Optional[Label] = None

    # ── 生命周期 ──────────────────────────────────────

    def enter(self, **kwargs) -> None:
        self._page = 0
        self._tab = _TAB_RELICS
        self._load_data()
        self._widgets.clear()
        self._build_static_ui()
        self._refresh_content()
        logger.info("进入图鉴场景")

    def exit(self) -> None:
        logger.info("离开图鉴场景")

    # ── 数据加载 ──────────────────────────────────────

    def _load_data(self) -> None:
        # 遗物
        try:
            registry = RelicRegistry.instance()
            if not registry.is_loaded:
                registry.load_all()
            self._relics_data = sorted(
                [(r.id, r.name, r.rarity, r.description)
                 for r in registry.all_relics()],
                key=lambda t: (_rarity_order(t[2]), t[1]),
            )
        except Exception as exc:
            logger.warning("加载遗物图鉴失败: %s", exc)
            self._relics_data = []

        # 卡牌
        try:
            cards = ConfigLoader().load_all_cards()
            self._cards_data = sorted(
                [(cid, cfg.get("name", cid),
                  cfg.get("rarity", "common"),
                  cfg.get("description", ""))
                 for cid, cfg in cards.items()],
                key=lambda t: (_rarity_order(t[2]), t[1]),
            )
        except Exception as exc:
            logger.warning("加载卡牌图鉴失败: %s", exc)
            self._cards_data = []

    def _seen_set(self) -> set:
        meta = self.game.save_manager.load_meta_progress()
        return set(meta.seen_relics if self._tab == _TAB_RELICS else meta.seen_cards)

    def _current_data(self) -> List[Tuple[str, str, str, str]]:
        return self._relics_data if self._tab == _TAB_RELICS else self._cards_data

    def _total_pages(self) -> int:
        n = len(self._current_data())
        return max(1, (n + _ITEMS_PER_PAGE - 1) // _ITEMS_PER_PAGE)

    # ── UI 构建 ────────────────────────────────────────

    def _build_static_ui(self) -> None:
        # 背景
        bg = Panel(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
                   bg_color=COLOR_BG_DARK, border_color=None, border_width=0)
        self._widgets.append(bg)

        # 中央面板
        panel = Panel(_PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H,
                      bg_color=COLOR_BG_LIGHT, border_color=COLOR_EPIC,
                      border_width=2, border_radius=10)
        self._widgets.append(panel)

        # 标题
        title = Label(_PANEL_X, _PANEL_Y + 16, _PANEL_W, 40,
                      text="冒险者图鉴",
                      font_size=FONT_SIZE_H1, color=COLOR_EPIC,
                      align="center", bold=True)
        self._widgets.append(title)

        # ── 标签页按钮 ──
        tab_y = _PANEL_Y + 70
        tab_w = 160
        gap = 16
        tabs_total = tab_w * 2 + gap
        tab_x_start = _PANEL_X + (_PANEL_W - tabs_total) // 2

        self._tab_btn_relics = Button(
            tab_x_start, tab_y, tab_w, 36, text="遗物",
            font_size=FONT_SIZE_BODY,
            on_click=lambda: self._switch_tab(_TAB_RELICS),
        )
        self._tab_btn_cards = Button(
            tab_x_start + tab_w + gap, tab_y, tab_w, 36, text="卡牌",
            font_size=FONT_SIZE_BODY,
            on_click=lambda: self._switch_tab(_TAB_CARDS),
        )
        self._widgets.extend([self._tab_btn_relics, self._tab_btn_cards])
        self._update_tab_styles()

        # 收集进度
        self._progress_label = Label(
            _PANEL_X + 20, tab_y + 4, 220, 28,
            text="", font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY, align="left",
        )
        self._widgets.append(self._progress_label)

        # 翻页按钮
        page_y = _PANEL_Y + _PANEL_H - 60
        prev_btn = Button(
            _PANEL_X + 30, page_y, 80, 36, text="<",
            font_size=FONT_SIZE_H3,
            on_click=self._on_prev_page,
        )
        next_btn = Button(
            _PANEL_X + _PANEL_W - 110, page_y, 80, 36, text=">",
            font_size=FONT_SIZE_H3,
            on_click=self._on_next_page,
        )
        self._widgets.extend([prev_btn, next_btn])
        self._page_label = Label(
            _PANEL_X + 130, page_y + 4, _PANEL_W - 260, 28,
            text="第 1 / 1 页", font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY, align="center",
        )
        self._widgets.append(self._page_label)

        # 返回按钮
        back_btn = Button(
            _PANEL_X + (_PANEL_W - 200) // 2, _PANEL_Y + _PANEL_H - 110,
            200, 36, text="返回主菜单",
            font_size=FONT_SIZE_BODY,
            on_click=self._on_back,
        )
        self._widgets.append(back_btn)

        # 内容区分隔线
        div = Panel(_PANEL_X + 20, _PANEL_Y + 116, _PANEL_W - 40, 1,
                    bg_color=COLOR_DIVIDER, border_color=None, border_width=0)
        self._widgets.append(div)

        # 当前内容控件容器（动态部分由 refresh 重新生成）
        self._content_widgets: list = []

    def _refresh_content(self) -> None:
        # 清掉旧的内容控件
        for w in self._content_widgets:
            try:
                self._widgets.remove(w)
            except ValueError:
                pass
        self._content_widgets = []

        seen = self._seen_set()
        data = self._current_data()
        total_pages = self._total_pages()
        self._page = max(0, min(self._page, total_pages - 1))
        start = self._page * _ITEMS_PER_PAGE
        page_items = data[start:start + _ITEMS_PER_PAGE]

        content_x = _PANEL_X + 30
        content_y = _PANEL_Y + 130
        content_w = _PANEL_W - 60

        for i, (item_id, name, rarity, desc) in enumerate(page_items):
            row_y = content_y + i * _ITEM_ROW_H
            self._build_item_row(content_x, row_y, content_w, item_id, name,
                                 rarity, desc, item_id in seen)

        # 翻页 / 进度文本
        if self._page_label:
            self._page_label.text = f"第 {self._page + 1} / {total_pages} 页"
        if self._progress_label:
            seen_count = sum(1 for x in data if x[0] in seen)
            self._progress_label.text = f"收集进度：{seen_count} / {len(data)}"

    def _build_item_row(self, x: int, y: int, w: int,
                        item_id: str, name: str, rarity: str, desc: str,
                        seen: bool) -> None:
        # 行背景框
        row_bg = Panel(x, y, w, _ITEM_ROW_H - 8,
                       bg_color=(36, 38, 60), border_color=COLOR_DIVIDER,
                       border_width=1, border_radius=4)
        self._content_widgets.append(row_bg)
        self._widgets.append(row_bg)

        # 稀有度色块
        rcolor = RARITY_COLORS.get(rarity, COLOR_WHITE)
        rarity_chip = Panel(x + 6, y + 4, 8, _ITEM_ROW_H - 16,
                            bg_color=rcolor, border_color=None, border_width=0,
                            border_radius=2)
        self._content_widgets.append(rarity_chip)
        self._widgets.append(rarity_chip)

        # 名称
        display_name = name if seen else "???"
        name_color = rcolor if seen else COLOR_TEXT_SECONDARY
        name_label = Label(
            x + 24, y + 6, int(w * 0.30), 24,
            text=display_name, font_size=FONT_SIZE_BODY,
            color=name_color, align="left", bold=True,
        )
        self._content_widgets.append(name_label)
        self._widgets.append(name_label)

        # 稀有度文本
        rarity_text = _RARITY_DISPLAY.get(rarity, rarity)
        r_label = Label(
            x + int(w * 0.34), y + 6, 80, 24,
            text=rarity_text, font_size=FONT_SIZE_CAPTION,
            color=rcolor, align="left",
        )
        self._content_widgets.append(r_label)
        self._widgets.append(r_label)

        # 描述
        display_desc = desc if seen else "尚未在轮回中遇到该条目"
        desc_label = Label(
            x + 24, y + 28, w - 30, 18,
            text=display_desc, font_size=FONT_SIZE_CAPTION,
            color=COLOR_WHITE if seen else COLOR_TEXT_SECONDARY,
            align="left",
        )
        self._content_widgets.append(desc_label)
        self._widgets.append(desc_label)

    # ── 操作回调 ──────────────────────────────────────

    def _switch_tab(self, tab: str) -> None:
        if tab == self._tab:
            return
        self._tab = tab
        self._page = 0
        self._update_tab_styles()
        self._refresh_content()

    def _update_tab_styles(self) -> None:
        if self._tab_btn_relics:
            self._tab_btn_relics.text = "▶ 遗物" if self._tab == _TAB_RELICS else "  遗物"
        if self._tab_btn_cards:
            self._tab_btn_cards.text = "▶ 卡牌" if self._tab == _TAB_CARDS else "  卡牌"

    def _on_prev_page(self) -> None:
        self._page = max(0, self._page - 1)
        self._refresh_content()

    def _on_next_page(self) -> None:
        self._page = min(self._total_pages() - 1, self._page + 1)
        self._refresh_content()

    def _on_back(self) -> None:
        self.game.state_machine.change(GameState.MAIN_MENU)

    # ── 事件 / 更新 / 渲染 ────────────────────────────

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._on_back()
                return
            if event.key in (pygame.K_LEFT, pygame.K_PAGEUP):
                self._on_prev_page()
                return
            if event.key in (pygame.K_RIGHT, pygame.K_PAGEDOWN):
                self._on_next_page()
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
        surface.fill(COLOR_BG_DARK)
        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)


# ── 工具 ──────────────────────────────────────────────────

_RARITY_DISPLAY = {
    "common":    "普通",
    "rare":      "稀有",
    "epic":      "史诗",
    "legendary": "传说",
}

_RARITY_ORDER = {"common": 0, "rare": 1, "epic": 2, "legendary": 3}


def _rarity_order(r: str) -> int:
    return _RARITY_ORDER.get(r, 99)
