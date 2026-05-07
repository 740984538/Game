"""
游戏结束场景 - 对应开发计划 8-12，文档 §2.2.1 死亡流程

进入方式：
    self.game.state_machine.change(
        GameState.GAME_OVER,
        reason="death" | "abandon" | ...,
        run_stats=dict,             # 可选；为空时自动从 run_state 读取
    )

完成标志（开发计划 8-12）：
  - 显示"游戏结束"标题
  - 显示本局统计：到达层数、击杀数量、收集遗物、打出卡牌数
  - 显示死亡原因（被哪个敌人击杀）
  - 展示本局获得的灵魂碎片数量
  - 有"返回主菜单"按钮
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
    COLOR_WHITE, COLOR_GOLD, COLOR_DANGER,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


_PANEL_W = 600
_PANEL_H = 520
_PANEL_X = (SCREEN_WIDTH - _PANEL_W) // 2
_PANEL_Y = (SCREEN_HEIGHT - _PANEL_H) // 2

# 灵魂碎片转换比例（每击杀给 1，每层给 5，BOSS 给 20）
_SHARDS_PER_KILL = 1
_SHARDS_PER_FLOOR = 5
_SHARDS_PER_BOSS = 20
_SHARDS_PER_ELITE = 5


class GameOverScene(BaseScene):
    """死亡 / 放弃 结算界面"""

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._reason: str = "death"
        self._stats_dict: dict = {}
        self._earned_shards: int = 0
        self._built_baseline: bool = False

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def enter(self, **kwargs) -> None:
        self._reason = kwargs.get("reason", "death")
        explicit = kwargs.get("run_stats")

        if isinstance(explicit, dict):
            self._stats_dict = dict(explicit)
        else:
            self._stats_dict = self._collect_stats_from_run_state()

        self._earned_shards = self._calc_soul_shards(self._stats_dict)

        # 阶段 9-3：将奖励写入元进度，并刷新图鉴
        self._apply_meta_rewards()

        # 阶段 9-2：清掉当局存档（既然死了就不能继续了）
        self._cleanup_run_save()

        # 重建 UI 以反映新数据
        self._widgets.clear()
        self._build_ui()
        logger.info(
            "进入游戏结束场景: 原因=%s, shards=%d, stats=%s",
            self._reason, self._earned_shards, self._stats_dict,
        )

    def _apply_meta_rewards(self) -> None:
        """阶段 9-3：把灵魂碎片累加到元进度，记录已收集遗物到图鉴"""
        sm = getattr(self.game, "save_manager", None)
        if sm is None:
            return
        try:
            if self._earned_shards > 0:
                sm.add_soul_shards(self._earned_shards)
            sm.record_run_finished(victory=False)
            # 把本局收集到的遗物记入图鉴
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
        logger.info("离开游戏结束场景")

    # ── 数据组装 ──────────────────────────────────────────────────────────

    def _collect_stats_from_run_state(self) -> dict:
        try:
            rs = self.game.run_state
        except AttributeError:
            return {}
        d = {
            "character_id": rs.character_id,
            "current_floor": rs.current_floor,
            "floors_cleared": rs.stats.floors_cleared,
            "rooms_cleared": rs.stats.rooms_cleared,
            "combats_won": rs.stats.combats_won,
            "elite_kills": rs.stats.elite_kills,
            "bosses_killed": rs.stats.bosses_killed,
            "total_kills": rs.stats.total_kills,
            "cards_played": rs.stats.cards_played,
            "relics_collected": rs.stats.relics_collected,
            "gold_earned": rs.stats.gold_earned,
            "killed_by": rs.stats.last_killed_by,
            "relics": rs.get_relic_ids(),
        }
        return d

    def _calc_soul_shards(self, stats: dict) -> int:
        return (
            stats.get("total_kills", 0) * _SHARDS_PER_KILL
            + stats.get("floors_cleared", 0) * _SHARDS_PER_FLOOR
            + stats.get("bosses_killed", 0) * _SHARDS_PER_BOSS
            + stats.get("elite_kills", 0) * _SHARDS_PER_ELITE
        )

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 全屏背景
        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK,
            border_color=None, border_width=0,
        )
        self._widgets.append(bg)

        # 中央面板
        panel = Panel(
            _PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_DANGER,
            border_width=3,
            border_radius=12,
        )
        self._widgets.append(panel)

        # 标题
        title_text = "游戏结束" if self._reason != "abandon" else "局已放弃"
        title = Label(
            _PANEL_X, _PANEL_Y + 24, _PANEL_W, 50,
            text=title_text,
            font_size=FONT_SIZE_H1,
            color=COLOR_DANGER,
            align="center", bold=True,
        )
        self._widgets.append(title)

        # 副标题（角色名/死因）
        char_id = self._stats_dict.get("character_id", "")
        killed_by = self._stats_dict.get("killed_by", "")
        if self._reason == "abandon":
            subtitle = f"主角：{char_id}    （主动放弃）"
        elif killed_by:
            subtitle = f"主角：{char_id}    被 {killed_by} 击败"
        else:
            subtitle = f"主角：{char_id}"

        subtitle_label = Label(
            _PANEL_X, _PANEL_Y + 80, _PANEL_W, 26,
            text=subtitle,
            font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self._widgets.append(subtitle_label)

        # 分割线
        divider = Panel(
            _PANEL_X + 60, _PANEL_Y + 116, _PANEL_W - 120, 2,
            bg_color=COLOR_DIVIDER, border_color=None, border_width=0,
        )
        self._widgets.append(divider)

        # 统计列表
        rows: List[tuple] = [
            ("到达层数",   f"第 {self._stats_dict.get('current_floor', 1)} 层"),
            ("已清房间",   f"{self._stats_dict.get('rooms_cleared', 0)} 间"),
            ("击杀总数",   f"{self._stats_dict.get('total_kills', 0)} 个"),
            ("精英击杀",   f"{self._stats_dict.get('elite_kills', 0)} 个"),
            ("BOSS 击杀",  f"{self._stats_dict.get('bosses_killed', 0)} 个"),
            ("打出卡牌",   f"{self._stats_dict.get('cards_played', 0)} 张"),
            ("收集遗物",   f"{self._stats_dict.get('relics_collected', 0)} 件"),
            ("总获金币",   f"{self._stats_dict.get('gold_earned', 0)} G"),
        ]
        self._add_stats_rows(rows)

        # 灵魂碎片奖励
        shards_y = _PANEL_Y + 380
        shards_label = Label(
            _PANEL_X + 40, shards_y, _PANEL_W - 80, 30,
            text=f"获得灵魂碎片：+{self._earned_shards}",
            font_size=FONT_SIZE_H3,
            color=COLOR_GOLD,
            align="center", bold=True,
        )
        self._widgets.append(shards_label)

        # 按钮区
        btn_w = 220
        btn_h = 44
        btn_y = _PANEL_Y + _PANEL_H - 64
        btn_gap = 16
        center_x = _PANEL_X + _PANEL_W // 2

        retry_btn = Button(
            center_x - btn_w - btn_gap // 2, btn_y, btn_w, btn_h,
            text="再来一局",
            font_size=FONT_SIZE_H3,
            on_click=self._on_retry,
            normal_bg=(50, 30, 30),
            hover_bg=(80, 50, 50),
            border_color=COLOR_TEXT_PRIMARY,
        )
        self._widgets.append(retry_btn)

        menu_btn = Button(
            center_x + btn_gap // 2, btn_y, btn_w, btn_h,
            text="返回主菜单",
            font_size=FONT_SIZE_H3,
            on_click=self._on_main_menu,
        )
        self._widgets.append(menu_btn)

    def _add_stats_rows(self, rows: List[tuple]) -> None:
        # 两列布局
        row_h = 28
        col_w = (_PANEL_W - 80) // 2
        start_x = _PANEL_X + 40
        start_y = _PANEL_Y + 134

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

    # ── 按钮回调 ──────────────────────────────────────────────────────────

    def _on_retry(self) -> None:
        # 标记上一局结束并跳转角色选择
        if hasattr(self.game, "run_state"):
            self.game.run_state.end_run()
        self.game.state_machine.change(GameState.CHARACTER_SELECT)

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
        for widget in self._widgets:
            widget.update(dt)

    def render(self, surface) -> None:
        if not _pygame_available:
            return
        surface.fill(COLOR_BG_DARK)
        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)
