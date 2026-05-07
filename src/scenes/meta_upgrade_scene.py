"""
局外灵魂碎片消费场景 - 阶段 9-4

从主菜单进入，提供：
- 显示当前灵魂碎片数量
- 角色解锁列表（已解锁打勾，未解锁显示价格 / 解锁按钮）
- 永久强化（初始 HP+ / 初始金币+ / 初始能量+ 等，等级递增）

数据来源：``self.game.save_manager``（单例）+ ``CharacterRegistry``。
对元进度的修改会立刻持久化。
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
from src.entities.player.character_stats import CharacterRegistry
from src.utils.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_DIVIDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_WHITE, COLOR_GOLD,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


# ── 永久强化项配置 ─────────────────────────────────
# (key, 名称, 描述模板, 每级价格, 最大等级)
PERM_UPGRADES = [
    ("hp_bonus",     "初始生命强化",  "+5 初始最大HP / 级", 80, 10),
    ("gold_bonus",   "初始金币强化",  "+20 初始金币 / 级",  60, 10),
    ("essence_bonus", "初始精华强化", "+1 初始精华 / 级",   120, 5),
    ("relic_chance", "幸运拾荒",     "+5% 普通战斗遗物掉率 / 级", 100, 5),
]

_PANEL_W = 1080
_PANEL_H = 600
_PANEL_X = (SCREEN_WIDTH - _PANEL_W) // 2
_PANEL_Y = (SCREEN_HEIGHT - _PANEL_H) // 2


class MetaUpgradeScene(BaseScene):
    """局外强化界面"""

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._info_label: Optional[Label] = None
        self._shards_label: Optional[Label] = None
        # 行 -> (data, button, info_label) 映射，用于刷新
        self._char_rows: list = []
        self._upgrade_rows: list = []

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def enter(self, **kwargs) -> None:
        registry = CharacterRegistry.instance()
        if not registry.is_loaded:
            registry.load_all()
        self._widgets.clear()
        self._char_rows.clear()
        self._upgrade_rows.clear()
        self._build_ui()
        logger.info("进入局外强化场景")

    def exit(self) -> None:
        # 离开时落盘元进度
        try:
            self.game.save_manager.save_meta_progress(self._meta())
        except Exception as exc:
            logger.warning("保存元进度失败: %s", exc)
        logger.info("离开局外强化场景")

    # ── 数据快捷访问 ─────────────────────────────────────────────────────

    def _meta(self):
        return self.game.save_manager.load_meta_progress()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 背景
        bg = Panel(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
                   bg_color=COLOR_BG_DARK, border_color=None, border_width=0)
        self._widgets.append(bg)

        # 中央面板
        panel = Panel(_PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H,
                      bg_color=COLOR_BG_LIGHT, border_color=COLOR_GOLD,
                      border_width=2, border_radius=10)
        self._widgets.append(panel)

        # 标题
        title = Label(_PANEL_X, _PANEL_Y + 20, _PANEL_W, 44,
                      text="灵魂祭坛 · 局外强化",
                      font_size=FONT_SIZE_H1, color=COLOR_GOLD,
                      align="center", bold=True)
        self._widgets.append(title)

        # 灵魂碎片数量
        meta = self._meta()
        self._shards_label = Label(
            _PANEL_X, _PANEL_Y + 70, _PANEL_W, 28,
            text=f"灵魂碎片：{meta.soul_shards}",
            font_size=FONT_SIZE_H3, color=COLOR_TEXT_PRIMARY,
            align="center", bold=True,
        )
        self._widgets.append(self._shards_label)

        # 分割线
        div = Panel(_PANEL_X + 40, _PANEL_Y + 110, _PANEL_W - 80, 1,
                    bg_color=COLOR_DIVIDER, border_color=None, border_width=0)
        self._widgets.append(div)

        # ── 左侧：角色解锁 ──
        col_w = (_PANEL_W - 80) // 2
        col_left_x = _PANEL_X + 30
        col_top_y = _PANEL_Y + 130

        char_title = Label(col_left_x, col_top_y, col_w, 30,
                           text="解锁角色", font_size=FONT_SIZE_H2,
                           color=COLOR_WHITE, align="left", bold=True)
        self._widgets.append(char_title)

        registry = CharacterRegistry.instance()
        chars = sorted(registry.all_characters(), key=lambda c: getattr(c, "unlock_cost", 0))
        row_y = col_top_y + 44
        for char in chars:
            self._build_character_row(col_left_x, row_y, col_w, char)
            row_y += 60

        # ── 右侧：永久强化 ──
        col_right_x = _PANEL_X + _PANEL_W // 2 + 10
        upg_title = Label(col_right_x, col_top_y, col_w, 30,
                          text="永久强化", font_size=FONT_SIZE_H2,
                          color=COLOR_WHITE, align="left", bold=True)
        self._widgets.append(upg_title)

        row_y = col_top_y + 44
        for upg in PERM_UPGRADES:
            self._build_upgrade_row(col_right_x, row_y, col_w, upg)
            row_y += 60

        # ── 提示 ──
        self._info_label = Label(
            _PANEL_X + 40, _PANEL_Y + _PANEL_H - 100, _PANEL_W - 80, 24,
            text="点击「解锁」消耗灵魂碎片获得对应内容", font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY, align="center",
        )
        self._widgets.append(self._info_label)

        # ── 返回按钮 ──
        back_btn = Button(
            _PANEL_X + (_PANEL_W - 220) // 2,
            _PANEL_Y + _PANEL_H - 64,
            220, 44,
            text="返回主菜单", font_size=FONT_SIZE_H3,
            on_click=self._on_back,
        )
        self._widgets.append(back_btn)

    def _build_character_row(self, x: int, y: int, w: int, char) -> None:
        meta = self._meta()
        unlocked = char.id in meta.unlocked_characters

        name_label = Label(
            x, y, int(w * 0.40), 36,
            text=char.name, font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE, align="left", bold=True,
        )
        self._widgets.append(name_label)

        cost = int(getattr(char, "unlock_cost", 0))
        info_text = "已解锁" if unlocked else f"需 {cost} 碎片"
        info_color = (120, 200, 120) if unlocked else COLOR_TEXT_SECONDARY
        info_label = Label(
            x + int(w * 0.40), y, int(w * 0.30), 36,
            text=info_text, font_size=FONT_SIZE_BODY,
            color=info_color, align="left",
        )
        self._widgets.append(info_label)

        btn_x = x + int(w * 0.72)
        btn_w = int(w * 0.26)
        if unlocked:
            btn = Button(btn_x, y + 2, btn_w, 32, text="已拥有",
                         on_click=lambda: None)
            btn.enabled = False
        else:
            def _on_unlock(c=char):
                self._try_unlock_character(c)
            btn = Button(btn_x, y + 2, btn_w, 32, text="解锁",
                         on_click=_on_unlock,
                         normal_bg=(40, 60, 40), hover_bg=(60, 100, 60),
                         border_color=(80, 200, 80))
        self._widgets.append(btn)

        self._char_rows.append((char, btn, info_label))

    def _build_upgrade_row(self, x: int, y: int, w: int, upg: tuple) -> None:
        key, name, desc, base_cost, max_lvl = upg
        meta = self._meta()
        level = int(meta.perm_upgrades.get(key, 0))

        name_label = Label(
            x, y, int(w * 0.42), 22,
            text=f"{name} Lv.{level}/{max_lvl}",
            font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE, align="left", bold=True,
        )
        self._widgets.append(name_label)

        desc_label = Label(
            x, y + 22, int(w * 0.70), 18,
            text=desc, font_size=14,
            color=COLOR_TEXT_SECONDARY, align="left",
        )
        self._widgets.append(desc_label)

        cost = base_cost * (level + 1)
        btn_x = x + int(w * 0.72)
        btn_w = int(w * 0.26)
        if level >= max_lvl:
            btn = Button(btn_x, y + 4, btn_w, 32, text="已满级",
                         on_click=lambda: None)
            btn.enabled = False
        else:
            def _on_buy(k=key, c=cost):
                self._try_buy_upgrade(k, c)
            btn = Button(btn_x, y + 4, btn_w, 32, text=f"升级 ({cost})",
                         on_click=_on_buy,
                         normal_bg=(60, 50, 20), hover_bg=(100, 80, 30),
                         border_color=COLOR_GOLD)
        self._widgets.append(btn)

        self._upgrade_rows.append((key, name_label, btn))

    # ── 操作 ──────────────────────────────────────────────────────────────

    def _try_unlock_character(self, char) -> None:
        meta = self._meta()
        cost = int(getattr(char, "unlock_cost", 0))
        if char.id in meta.unlocked_characters:
            self._set_info("该角色已解锁", warning=True)
            return
        if meta.soul_shards < cost:
            self._set_info(f"灵魂碎片不足，还差 {cost - meta.soul_shards}", warning=True)
            return
        meta.soul_shards -= cost
        meta.unlock_character(char.id)
        self.game.save_manager.save_meta_progress(meta)
        self._set_info(f"已解锁角色「{char.name}」！")
        # 重建 UI 反映状态
        self._refresh()

    def _try_buy_upgrade(self, key: str, cost: int) -> None:
        meta = self._meta()
        if meta.soul_shards < cost:
            self._set_info(f"灵魂碎片不足，还差 {cost - meta.soul_shards}", warning=True)
            return
        meta.soul_shards -= cost
        meta.perm_upgrades[key] = int(meta.perm_upgrades.get(key, 0)) + 1
        self.game.save_manager.save_meta_progress(meta)
        self._set_info(f"强化成功！当前等级 {meta.perm_upgrades[key]}")
        self._refresh()

    def _set_info(self, text: str, warning: bool = False) -> None:
        if self._info_label:
            self._info_label.text = text
            self._info_label.color = (220, 90, 90) if warning else (120, 200, 120)

    def _refresh(self) -> None:
        # 简单粗暴：重建整个 UI
        self._widgets.clear()
        self._char_rows.clear()
        self._upgrade_rows.clear()
        self._build_ui()

    def _on_back(self) -> None:
        self.game.state_machine.change(GameState.MAIN_MENU)

    # ── 事件 / 更新 / 渲染 ────────────────────────────────────────────────

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_back()
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
