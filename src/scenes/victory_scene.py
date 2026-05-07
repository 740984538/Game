"""
胜利场景 - 对应开发计划 8-13，文档 §2.2.1 击败最终BOSS流程

进入方式（CombatScene 击败最终 BOSS 后）::

    self.game.state_machine.change(
        GameState.VICTORY,
        run_stats=dict,             # 可选；缺省时从 run_state 读取
    )

完成标志（开发计划 8-13）：
  - 显示"胜利"标题和庆祝效果（金色脉动）
  - 显示本局通关统计（时间、层数、卡组、遗物）
  - 展示获得的灵魂碎片奖励（高于普通结算）
  - "返回主菜单"按钮
"""
from __future__ import annotations

import logging
import math
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
    COLOR_WHITE, COLOR_GOLD,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


_PANEL_W = 640
_PANEL_H = 540
_PANEL_X = (SCREEN_WIDTH - _PANEL_W) // 2
_PANEL_Y = (SCREEN_HEIGHT - _PANEL_H) // 2

# 通关奖励（比 GameOver 高 50%）
_VICTORY_BONUS_MULT = 1.5
_SHARDS_PER_KILL = 1
_SHARDS_PER_FLOOR = 5
_SHARDS_PER_BOSS = 20
_SHARDS_PER_ELITE = 5


class VictoryScene(BaseScene):
    """通关结算场景"""

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._stats_dict: dict = {}
        self._earned_shards: int = 0
        self._title_label: Optional[Label] = None
        self._anim_time: float = 0.0
        self._title_base_color = COLOR_GOLD

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def enter(self, **kwargs) -> None:
        explicit = kwargs.get("run_stats")
        if isinstance(explicit, dict):
            self._stats_dict = dict(explicit)
        else:
            self._stats_dict = self._collect_stats_from_run_state()

        self._earned_shards = self._calc_soul_shards(self._stats_dict)

        # 阶段 9-3：通关奖励 + 元进度更新
        self._apply_meta_rewards()
        # 阶段 9-2：清掉当局存档
        self._cleanup_run_save()

        self._widgets.clear()
        self._anim_time = 0.0
        self._build_ui()
        logger.info(
            "进入胜利场景: shards=%d stats=%s",
            self._earned_shards, self._stats_dict,
        )

    def _apply_meta_rewards(self) -> None:
        sm = getattr(self.game, "save_manager", None)
        if sm is None:
            return
        try:
            if self._earned_shards > 0:
                sm.add_soul_shards(self._earned_shards)
            sm.record_run_finished(victory=True)
            meta = sm.load_meta_progress()
            for rid in self._stats_dict.get("relics", []) or []:
                meta.see_relic(rid)
            sm.save_meta_progress(meta)
        except Exception as exc:
            logger.warning("写入元进度失败: %s", exc)

    def _cleanup_run_save(self) -> None:
        sm = getattr(self.game, "save_manager", None)
        if sm is None:
            return
        try:
            sm.delete_run_state()
        except Exception:
            pass

    def exit(self) -> None:
        logger.info("离开胜利场景")

    # ── 数据 ──────────────────────────────────────────────────────────────

    def _collect_stats_from_run_state(self) -> dict:
        try:
            rs = self.game.run_state
        except AttributeError:
            return {}
        return {
            "character_id": rs.character_id,
            "current_floor": rs.current_floor,
            "floors_cleared": rs.stats.floors_cleared,
            "rooms_cleared": rs.stats.rooms_cleared,
            "total_kills": rs.stats.total_kills,
            "elite_kills": rs.stats.elite_kills,
            "bosses_killed": rs.stats.bosses_killed,
            "cards_played": rs.stats.cards_played,
            "relics_collected": rs.stats.relics_collected,
            "gold_earned": rs.stats.gold_earned,
            "play_seconds": rs.stats.play_seconds,
            "deck_size": len(rs.deck),
            "relics": rs.get_relic_ids(),
        }

    def _calc_soul_shards(self, stats: dict) -> int:
        base = (
            stats.get("total_kills", 0) * _SHARDS_PER_KILL
            + stats.get("floors_cleared", 0) * _SHARDS_PER_FLOOR
            + stats.get("bosses_killed", 0) * _SHARDS_PER_BOSS
            + stats.get("elite_kills", 0) * _SHARDS_PER_ELITE
        )
        return int(base * _VICTORY_BONUS_MULT)

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 背景
        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK,
            border_color=None, border_width=0,
        )
        self._widgets.append(bg)

        # 中央面板（金色边框）
        panel = Panel(
            _PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_GOLD,
            border_width=4,
            border_radius=14,
        )
        self._widgets.append(panel)

        # 标题（脉动）
        self._title_label = Label(
            _PANEL_X, _PANEL_Y + 24, _PANEL_W, 60,
            text="✦  胜  利  ✦",
            font_size=FONT_SIZE_H1,
            color=COLOR_GOLD,
            align="center", bold=True,
        )
        self._widgets.append(self._title_label)

        # 副标题
        char_id = self._stats_dict.get("character_id", "")
        subtitle_text = f"主角：{char_id}    通关 第 {self._stats_dict.get('current_floor', 1)} 层"
        subtitle = Label(
            _PANEL_X, _PANEL_Y + 90, _PANEL_W, 28,
            text=subtitle_text,
            font_size=FONT_SIZE_H3,
            color=COLOR_TEXT_PRIMARY,
            align="center",
        )
        self._widgets.append(subtitle)

        # 分割线
        divider = Panel(
            _PANEL_X + 80, _PANEL_Y + 130, _PANEL_W - 160, 2,
            bg_color=COLOR_GOLD, border_color=None, border_width=0,
        )
        self._widgets.append(divider)

        # 统计
        rows = [
            ("通关时间",   self._format_time(self._stats_dict.get("play_seconds", 0))),
            ("已清房间",   f"{self._stats_dict.get('rooms_cleared', 0)} 间"),
            ("击杀总数",   f"{self._stats_dict.get('total_kills', 0)} 个"),
            ("BOSS 击杀",  f"{self._stats_dict.get('bosses_killed', 0)} 个"),
            ("打出卡牌",   f"{self._stats_dict.get('cards_played', 0)} 张"),
            ("最终卡组",   f"{self._stats_dict.get('deck_size', 0)} 张"),
            ("收集遗物",   f"{self._stats_dict.get('relics_collected', 0)} 件"),
            ("总获金币",   f"{self._stats_dict.get('gold_earned', 0)} G"),
        ]
        self._add_stats_rows(rows, start_y=_PANEL_Y + 150)

        # 灵魂碎片
        shards_label = Label(
            _PANEL_X, _PANEL_Y + 400, _PANEL_W, 40,
            text=f"获得灵魂碎片：+{self._earned_shards}（含通关奖励 ×{_VICTORY_BONUS_MULT}）",
            font_size=FONT_SIZE_H3,
            color=COLOR_GOLD,
            align="center", bold=True,
        )
        self._widgets.append(shards_label)

        # 按钮
        btn_w = 240
        btn_h = 48
        btn_y = _PANEL_Y + _PANEL_H - 72
        center_x = _PANEL_X + _PANEL_W // 2

        menu_btn = Button(
            center_x - btn_w // 2, btn_y, btn_w, btn_h,
            text="返回主菜单",
            font_size=FONT_SIZE_H3,
            on_click=self._on_main_menu,
            normal_bg=(50, 40, 20),
            hover_bg=(90, 70, 30),
            border_color=COLOR_GOLD,
        )
        self._widgets.append(menu_btn)

    def _add_stats_rows(self, rows: List[tuple], start_y: int) -> None:
        row_h = 28
        col_w = (_PANEL_W - 80) // 2
        start_x = _PANEL_X + 40

        for i, (key, value) in enumerate(rows):
            col = i % 2
            row = i // 2
            x = start_x + col * col_w
            y = start_y + row * row_h

            key_label = Label(
                x, y, int(col_w * 0.55), row_h,
                text=key,
                font_size=FONT_SIZE_BODY,
                color=COLOR_TEXT_SECONDARY,
                align="left",
            )
            value_label = Label(
                x + int(col_w * 0.55), y, int(col_w * 0.45) - 10, row_h,
                text=value,
                font_size=FONT_SIZE_BODY,
                color=COLOR_WHITE,
                align="right", bold=True,
            )
            self._widgets.extend([key_label, value_label])

    @staticmethod
    def _format_time(seconds: float) -> str:
        seconds = int(seconds)
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    # ── 按钮回调 ──────────────────────────────────────────────────────────

    def _on_main_menu(self) -> None:
        if hasattr(self.game, "run_state"):
            self.game.run_state.end_run()
        self.game.state_machine.change(GameState.MAIN_MENU)

    # ── 事件 / 更新 / 渲染 ────────────────────────────────────────────────

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self._on_main_menu()
            return
        for widget in self._widgets:
            if widget.handle_event(event):
                break

    def update(self, dt: float) -> None:
        self._anim_time += dt
        # 标题脉动颜色
        if self._title_label:
            pulse = 0.5 + 0.5 * math.sin(self._anim_time * 2.5)
            r, g, b = COLOR_GOLD
            r = int(min(255, r * (0.85 + 0.15 * pulse)))
            g = int(min(255, g * (0.85 + 0.15 * pulse)))
            b = int(min(255, b * (0.85 + 0.15 * pulse)))
            self._title_label.color = (r, g, b)

        for widget in self._widgets:
            widget.update(dt)

    def render(self, surface) -> None:
        if not _pygame_available:
            return
        surface.fill(COLOR_BG_DARK)
        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)
