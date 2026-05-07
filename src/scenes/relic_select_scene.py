"""
遗物选择场景 - 对应开发计划 8-5，文档 §5.2 / §5.2.2

进入方式（由 CombatScene 在 BOSS / 精英战斗胜利后切换）::

    self.game.state_machine.change(
        GameState.RELIC_SELECT,
        relic_pool=["iron_will", "blood_rage", "fire_heart"],
        return_state=GameState.MAP_NAVIGATION,
        return_kwargs={"floor_number": 2, "character_id": "knight"},
        on_pick=lambda relic_id: ...,    # 可选回调
    )

完成标志（开发计划 8-5）：
  - 显示 N 张遗物卡（默认 3 张）
  - 显示遗物名称、稀有度、效果描述
  - 点击选择后获得遗物
  - 选择后返回地图（或调用方指定的状态）
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
from src.entities.relics.relic import RelicRegistry, Relic
from src.utils.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_DIVIDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_WHITE, COLOR_GOLD, COLOR_EPIC,
    RARITY_COLORS,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)
from src.utils.enums import GameState, Rarity

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


# ── 布局常量 ────────────────────────────────────────────────────────────────

_CARD_W = 280
_CARD_H = 360
_CARD_GAP = 30
_CENTER_X = SCREEN_WIDTH // 2
_CENTER_Y = SCREEN_HEIGHT // 2

_RARITY_LABELS = {
    "common":    "普通",
    "rare":      "稀有",
    "epic":      "史诗",
    "legendary": "传说",
}


# ═══════════════════════════════════════════════════════════════════════════════
# RelicCard - 单张遗物卡（容器组件）
# ═══════════════════════════════════════════════════════════════════════════════

class _RelicCard(Panel):
    """
    单个遗物卡片：背景面板 + 名称 + 稀有度标签 + 效果描述。
    点击触发回调。
    """

    def __init__(self, x: int, y: int, w: int, h: int,
                 relic: Relic, on_click) -> None:
        rarity_color = RARITY_COLORS.get(relic.rarity, COLOR_WHITE)
        super().__init__(
            x, y, w, h,
            bg_color=COLOR_BG_LIGHT,
            border_color=rarity_color,
            border_width=2,
            border_radius=10,
        )
        self._relic = relic
        self._on_click = on_click
        self._rarity_color = rarity_color
        self._hovered = False
        self._selected = False

        # 名称
        name_label = Label(
            x + 12, y + 18, w - 24, 36,
            text=relic.name,
            font_size=FONT_SIZE_H2,
            color=COLOR_WHITE,
            align="center", bold=True,
        )
        self.add_child(name_label)

        # 稀有度标签
        rarity_label = Label(
            x + 12, y + 60, w - 24, 24,
            text=_RARITY_LABELS.get(relic.rarity, relic.rarity),
            font_size=FONT_SIZE_BODY,
            color=rarity_color,
            align="center", bold=True,
        )
        self.add_child(rarity_label)

        # 分割线占位（用空 Panel 实现）
        divider = Panel(
            x + 30, y + 96, w - 60, 1,
            bg_color=COLOR_DIVIDER, border_color=None, border_width=0,
        )
        self.add_child(divider)

        # 描述（自动换行）
        desc_label = Label(
            x + 18, y + 110, w - 36, h - 170,
            text=relic.description or "（无描述）",
            font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY,
            align="center", wrap=True,
        )
        self.add_child(desc_label)

        # 效果数量标签（小提示）
        effect_count = len(relic.effects)
        effect_hint = Label(
            x + 12, y + h - 48, w - 24, 20,
            text=f"{effect_count} 个效果",
            font_size=FONT_SIZE_CAPTION,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self.add_child(effect_hint)

    @property
    def relic(self) -> Relic:
        return self._relic

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        # 选中时使用金色高亮边框
        self._border_color = COLOR_GOLD if value else self._rarity_color
        self._border_width = 4 if value else 2

    # 事件处理
    def handle_event(self, event) -> bool:
        if not self._visible or not self._enabled or not _pygame_available:
            return False

        if event.type == pygame.MOUSEMOTION:
            inside = self.contains_point(*event.pos)
            if inside != self._hovered:
                self._hovered = inside
                if not self._selected:
                    self._border_width = 3 if inside else 2

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.contains_point(*event.pos):
                if self._on_click:
                    self._on_click(self)
                return True

        return False

    def render(self, surface) -> None:
        if not self._visible or not _pygame_available:
            return

        # 背景：选中时略微提亮
        rect = pygame.Rect(self._x, self._y, self._width, self._height)
        bg = COLOR_BG_LIGHT if not self._hovered else (32, 48, 84)
        pygame.draw.rect(surface, bg, rect, border_radius=self._border_radius)

        # 边框
        if self._border_color is not None and self._border_width > 0:
            pygame.draw.rect(
                surface, self._border_color, rect,
                width=self._border_width,
                border_radius=self._border_radius,
            )

        # 子组件
        self._render_children(surface)


# ═══════════════════════════════════════════════════════════════════════════════
# RelicSelectScene
# ═══════════════════════════════════════════════════════════════════════════════

class RelicSelectScene(BaseScene):
    """
    遗物选择场景（开发计划 8-5）。

    进入参数（kwargs）：
      relic_pool:     List[str]        - 候选遗物 ID 列表（必传）
      count:          int              - 强制候选数量（默认 = len(relic_pool)）
      return_state:   GameState        - 选择/跳过后返回的状态（默认 MAP_NAVIGATION）
      return_kwargs:  dict             - 传给返回状态的 kwargs（默认空）
      on_pick:        Callable[[str], None]   - 选定后的回调
      allow_skip:     bool             - 是否允许跳过（默认 True）
      title:          str              - 自定义标题
    """

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._cards: List[_RelicCard] = []
        self._selected_card: Optional[_RelicCard] = None

        # 进入参数
        self._relic_pool: List[str] = []
        self._return_state: GameState = GameState.MAP_NAVIGATION
        self._return_kwargs: dict = {}
        self._on_pick = None
        self._allow_skip: bool = True
        self._title: str = "选择一件遗物"

        # 控制按钮
        self._confirm_btn: Optional[Button] = None
        self._skip_btn: Optional[Button] = None
        self._info_label: Optional[Label] = None

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def enter(self, **kwargs) -> None:
        # 兼容旧签名 `relic_pool=list, count=int`
        relic_pool = kwargs.get("relic_pool") or []
        count = kwargs.get("count")

        self._relic_pool = list(relic_pool)
        if count is not None and count > 0:
            self._relic_pool = self._relic_pool[:count]

        self._return_state = kwargs.get("return_state", GameState.MAP_NAVIGATION)
        self._return_kwargs = kwargs.get("return_kwargs", {}) or {}
        self._on_pick = kwargs.get("on_pick")
        self._allow_skip = bool(kwargs.get("allow_skip", True))
        self._title = kwargs.get("title", "选择一件遗物")

        # 确保注册表已加载（用于查询遗物详情）
        registry = RelicRegistry.instance()
        if not registry.is_loaded:
            try:
                registry.load_all()
            except Exception as exc:
                logger.warning("RelicRegistry 加载失败: %s", exc)

        # 重建 UI
        self._widgets.clear()
        self._cards.clear()
        self._selected_card = None
        self._build_ui()

        logger.info(
            "进入遗物选择场景: 候选=%s, 返回=%s",
            self._relic_pool, self._return_state,
        )

    def exit(self) -> None:
        self._widgets.clear()
        self._cards.clear()
        self._selected_card = None
        logger.info("离开遗物选择场景")

    # ── UI 构建 ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 背景
        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK, border_color=None, border_width=0,
        )
        self._widgets.append(bg)

        # 标题
        title_label = Label(
            _CENTER_X - 400, 40, 800, 48,
            text=self._title,
            font_size=FONT_SIZE_H1,
            color=COLOR_TEXT_PRIMARY,
            align="center", bold=True,
        )
        self._widgets.append(title_label)

        # 副标题/信息
        self._info_label = Label(
            _CENTER_X - 400, 96, 800, 24,
            text="点击卡片选择，再点确认获取该遗物",
            font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self._widgets.append(self._info_label)

        # 卡片
        self._build_cards()

        # 按钮
        self._build_buttons()

        # 错误提示（候选为空）
        if not self._cards:
            empty_label = Label(
                _CENTER_X - 200, _CENTER_Y - 12, 400, 24,
                text="（无可选遗物，已自动跳过）",
                font_size=FONT_SIZE_H3,
                color=COLOR_TEXT_SECONDARY,
                align="center",
            )
            self._widgets.append(empty_label)

    def _build_cards(self) -> None:
        registry = RelicRegistry.instance()

        # 收集合法的 Relic 对象
        relics: List[Relic] = []
        for rid in self._relic_pool:
            relic = registry.get(rid)
            if relic is None:
                # 注册表未加载或 id 不存在时，构造一个最小占位
                logger.warning("遗物 %s 不在注册表中", rid)
                continue
            relics.append(relic)

        if not relics:
            return

        n = len(relics)
        total_w = n * _CARD_W + (n - 1) * _CARD_GAP
        start_x = _CENTER_X - total_w // 2
        start_y = 150

        for i, relic in enumerate(relics):
            cx = start_x + i * (_CARD_W + _CARD_GAP)
            card = _RelicCard(
                cx, start_y, _CARD_W, _CARD_H,
                relic=relic,
                on_click=self._on_card_click,
            )
            self._cards.append(card)
            self._widgets.append(card)

    def _build_buttons(self) -> None:
        btn_w = 200
        btn_h = 48
        btn_y = SCREEN_HEIGHT - 80

        # 确认按钮（默认禁用）
        self._confirm_btn = Button(
            _CENTER_X - btn_w - 16, btn_y, btn_w, btn_h,
            text="确认获取",
            font_size=FONT_SIZE_H3,
            on_click=self._on_confirm,
            normal_bg=(30, 70, 30),
            hover_bg=(50, 110, 50),
            border_color=(60, 180, 60),
        )
        self._confirm_btn.enabled = False
        self._widgets.append(self._confirm_btn)

        # 跳过按钮
        skip_text = "跳过" if self._allow_skip else "无法跳过"
        self._skip_btn = Button(
            _CENTER_X + 16, btn_y, btn_w, btn_h,
            text=skip_text,
            font_size=FONT_SIZE_H3,
            on_click=self._on_skip,
        )
        self._skip_btn.enabled = self._allow_skip
        self._widgets.append(self._skip_btn)

    # ── 交互回调 ──────────────────────────────────────────────────────────

    def _on_card_click(self, card: _RelicCard) -> None:
        # 取消之前的选择
        if self._selected_card is not None and self._selected_card is not card:
            self._selected_card.selected = False

        card.selected = True
        self._selected_card = card

        if self._info_label:
            self._info_label.text = (
                f"已选中：{card.relic.name}（{_RARITY_LABELS.get(card.relic.rarity, card.relic.rarity)}）"
            )
            self._info_label.color = RARITY_COLORS.get(card.relic.rarity, COLOR_WHITE)

        if self._confirm_btn:
            self._confirm_btn.enabled = True

        logger.info("选中遗物: %s", card.relic.id)

    def _on_confirm(self) -> None:
        if self._selected_card is None:
            return
        relic_id = self._selected_card.relic.id
        logger.info("确认获取遗物: %s", relic_id)

        # 通知调用方
        if self._on_pick is not None:
            try:
                self._on_pick(relic_id)
            except Exception as exc:
                logger.exception("on_pick 回调失败: %s", exc)

        self._return(picked=relic_id)

    def _on_skip(self) -> None:
        if not self._allow_skip:
            return
        logger.info("跳过遗物选择")
        self._return(picked=None)

    def _return(self, picked: Optional[str]) -> None:
        """切换回返回状态，并在 kwargs 中附带选择结果"""
        kw = dict(self._return_kwargs)
        kw.setdefault("picked_relic", picked)
        self.game.state_machine.change(self._return_state, **kw)

    # ── 事件 / 更新 / 渲染 ────────────────────────────────────────────────

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return
        # 候选为空时按任意键返回
        if not self._cards:
            if event.type == pygame.KEYDOWN or (
                event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            ):
                self._return(picked=None)
                return

        # ESC 跳过
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._allow_skip:
                self._on_skip()
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
