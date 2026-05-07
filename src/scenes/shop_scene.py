"""
商店场景 - 对应开发计划 8-6，文档 §3.2.3

进入方式（由 MapNavigationScene 切换）::

    self.game.state_machine.change(
        GameState.SHOP,
        floor=floor, floor_number=N, character_id=..., daily=..., seed=..., node_id=...,
    )

完成标志（开发计划 8-6）：
  - 显示商店商品列表（遗物 + 卡牌）
  - 显示商品价格
  - 显示玩家金币
  - 点击购买，金币足够时获得商品
  - 有"离开商店"按钮
"""
from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional, TYPE_CHECKING

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
from src.generation.difficulty_scaler import DifficultyScaler
from src.utils.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_DIVIDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_WHITE, COLOR_GOLD, COLOR_DANGER,
    RARITY_COLORS,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


# ── 商店配置 ────────────────────────────────────────────────────────────────

NUM_RELIC_SLOTS: int = 3
NUM_CARD_SLOTS: int = 4

# 基础价格（按稀有度）
RELIC_BASE_PRICES: Dict[str, int] = {
    "common":    100,
    "rare":      180,
    "epic":      300,
    "legendary": 500,
}
CARD_BASE_PRICES: Dict[str, int] = {
    "attack":  60,
    "skill":   75,
    "ability": 100,
    "cursed":  20,   # 诅咒卡几乎不该卖，但便于回收
}

# 布局
_HEADER_H = 80
_RELIC_AREA_Y = _HEADER_H + 30
_RELIC_W = 220
_RELIC_H = 240
_CARD_AREA_Y = _RELIC_AREA_Y + _RELIC_H + 40
_CARD_W = 200
_CARD_H = 140


class _ShopItemWidget(Panel):
    """商店中的单个商品（遗物或卡牌）"""

    def __init__(self, x: int, y: int, w: int, h: int,
                 item_kind: str, item_id: str, name: str,
                 description: str, price: int,
                 border_color, on_buy) -> None:
        super().__init__(
            x, y, w, h,
            bg_color=COLOR_BG_LIGHT,
            border_color=border_color,
            border_width=2,
            border_radius=8,
        )
        self._item_kind = item_kind  # "relic" or "card"
        self._item_id = item_id
        self._price = price
        self._on_buy = on_buy
        self._sold = False
        self._affordable = True

        # 名称
        name_label = Label(
            x + 8, y + 10, w - 16, 28,
            text=name,
            font_size=FONT_SIZE_H3,
            color=COLOR_WHITE,
            align="center", bold=True,
        )
        self.add_child(name_label)

        # 描述
        desc_label = Label(
            x + 12, y + 44, w - 24, h - 110,
            text=description,
            font_size=FONT_SIZE_CAPTION,
            color=COLOR_TEXT_SECONDARY,
            align="center", wrap=True,
        )
        self.add_child(desc_label)

        # 价格 + 购买按钮
        self._price_label = Label(
            x + 8, y + h - 60, w - 16, 22,
            text=f"{price} G",
            font_size=FONT_SIZE_H3,
            color=COLOR_GOLD,
            align="center", bold=True,
        )
        self.add_child(self._price_label)

        self._buy_btn = Button(
            x + 16, y + h - 36, w - 32, 28,
            text="购买",
            font_size=FONT_SIZE_BODY,
            on_click=self._on_buy_clicked,
            normal_bg=(40, 70, 40),
            hover_bg=(60, 110, 60),
            border_color=(80, 180, 80),
        )
        self.add_child(self._buy_btn)

    def _on_buy_clicked(self) -> None:
        if self._sold or not self._affordable:
            return
        if self._on_buy:
            self._on_buy(self)

    @property
    def item_kind(self) -> str:
        return self._item_kind

    @property
    def item_id(self) -> str:
        return self._item_id

    @property
    def price(self) -> int:
        return self._price

    def mark_sold(self) -> None:
        self._sold = True
        self._buy_btn.text = "已售罄"
        self._buy_btn.enabled = False
        self._price_label.color = COLOR_TEXT_SECONDARY

    def set_affordable(self, can_buy: bool) -> None:
        if self._sold:
            return
        self._affordable = can_buy
        self._buy_btn.enabled = can_buy
        self._price_label.color = COLOR_GOLD if can_buy else COLOR_DANGER


class ShopScene(BaseScene):
    """商店场景：展示遗物 + 卡牌商品"""

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._items: List[_ShopItemWidget] = []
        self._gold_label: Optional[Label] = None
        self._info_label: Optional[Label] = None
        self._return_kwargs: dict = {}
        self._scaler = DifficultyScaler.from_config()

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def enter(self, **kwargs) -> None:
        self._return_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("room_type", "node_id")
        }
        floor_number = kwargs.get("floor_number", 1)
        seed = kwargs.get("seed", 0)
        node_id = kwargs.get("node_id", 0)

        # 商品池随种子+楼层+节点确定，避免每次进同一商店刷新
        rng = random.Random(seed * 100 + floor_number * 13 + node_id * 7 + 31)

        self._widgets.clear()
        self._items.clear()
        self._build_ui(rng, floor_number)

        # 触发遗物 on_shop_open（折扣等）
        try:
            from src.core.event_manager import event_manager
            event_manager.publish("on_shop_open")
        except Exception:
            pass

        self._update_affordability()
        logger.info("进入商店场景: floor=%d", floor_number)

    def exit(self) -> None:
        self._widgets.clear()
        self._items.clear()
        logger.info("离开商店场景")

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self, rng: random.Random, floor_number: int) -> None:
        # 背景
        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK,
            border_color=None, border_width=0,
        )
        self._widgets.append(bg)

        # 标题
        title = Label(
            0, 16, SCREEN_WIDTH, 40,
            text="商  店",
            font_size=FONT_SIZE_H1,
            color=COLOR_TEXT_PRIMARY,
            align="center", bold=True,
        )
        self._widgets.append(title)

        # 金币显示（右上角）
        self._gold_label = Label(
            SCREEN_WIDTH - 240, 22, 220, 30,
            text="",
            font_size=FONT_SIZE_H3,
            color=COLOR_GOLD,
            align="right", bold=True,
        )
        self._widgets.append(self._gold_label)

        # 离开按钮（左上角）
        leave_btn = Button(
            20, 20, 140, 36,
            text="离开商店",
            font_size=FONT_SIZE_BODY,
            on_click=self._on_leave,
        )
        self._widgets.append(leave_btn)

        # 遗物区标题
        relic_title = Label(
            40, _RELIC_AREA_Y - 24, 300, 22,
            text="◆ 遗物",
            font_size=FONT_SIZE_H3,
            color=COLOR_GOLD,
            align="left", bold=True,
        )
        self._widgets.append(relic_title)

        # 遗物商品
        self._build_relic_slots(rng, floor_number)

        # 卡牌区标题
        card_title = Label(
            40, _CARD_AREA_Y - 24, 300, 22,
            text="◆ 卡牌",
            font_size=FONT_SIZE_H3,
            color=(120, 180, 240),
            align="left", bold=True,
        )
        self._widgets.append(card_title)

        # 卡牌商品
        self._build_card_slots(rng, floor_number)

        # 信息提示
        self._info_label = Label(
            0, SCREEN_HEIGHT - 36, SCREEN_WIDTH, 24,
            text="点击商品进行购买",
            font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self._widgets.append(self._info_label)

        self._refresh_gold_label()

    def _build_relic_slots(self, rng: random.Random, floor_number: int) -> None:
        registry = RelicRegistry.instance()
        if not registry.is_loaded:
            try:
                registry.load_all()
            except Exception:
                return

        # 排除已持有
        owned = set(self._owned_relic_ids())
        candidates = [r for r in registry.all_relics() if r.id not in owned]
        if not candidates:
            return

        rng.shuffle(candidates)
        chosen = candidates[:NUM_RELIC_SLOTS]

        total_w = NUM_RELIC_SLOTS * _RELIC_W + (NUM_RELIC_SLOTS - 1) * 30
        start_x = (SCREEN_WIDTH - total_w) // 2

        for i, relic in enumerate(chosen):
            x = start_x + i * (_RELIC_W + 30)
            base_price = RELIC_BASE_PRICES.get(relic.rarity, 150)
            price = self._scaler.scale_price(base_price, floor=floor_number,
                                             difficulty=self._difficulty())
            border_color = RARITY_COLORS.get(relic.rarity, COLOR_DIVIDER)
            item = _ShopItemWidget(
                x, _RELIC_AREA_Y, _RELIC_W, _RELIC_H,
                item_kind="relic",
                item_id=relic.id,
                name=relic.name,
                description=relic.description,
                price=price,
                border_color=border_color,
                on_buy=self._on_buy_item,
            )
            self._items.append(item)
            self._widgets.append(item)

    def _build_card_slots(self, rng: random.Random, floor_number: int) -> None:
        try:
            from src.data.config_loader import ConfigLoader
            all_cards = ConfigLoader().load_all_cards()
        except Exception:
            return

        # 不卖诅咒卡
        candidates = [
            (cid, cfg) for cid, cfg in all_cards.items()
            if cfg.get("type") != "cursed"
        ]
        if not candidates:
            return

        rng.shuffle(candidates)
        chosen = candidates[:NUM_CARD_SLOTS]

        total_w = NUM_CARD_SLOTS * _CARD_W + (NUM_CARD_SLOTS - 1) * 20
        start_x = (SCREEN_WIDTH - total_w) // 2

        for i, (cid, cfg) in enumerate(chosen):
            x = start_x + i * (_CARD_W + 20)
            card_type = cfg.get("type", "skill")
            base_price = CARD_BASE_PRICES.get(card_type, 80)
            price = self._scaler.scale_price(base_price, floor=floor_number,
                                             difficulty=self._difficulty())

            type_color_map = {
                "attack": (180, 60, 60),
                "skill":  (60, 120, 200),
                "ability": (160, 80, 200),
                "cursed": (40, 40, 40),
            }
            border_color = type_color_map.get(card_type, COLOR_DIVIDER)

            name = cfg.get("name", cid)
            desc = cfg.get("description", "")
            cost = cfg.get("cost", 1)
            display_desc = f"费用 {cost}\n{desc}"

            item = _ShopItemWidget(
                x, _CARD_AREA_Y, _CARD_W, _CARD_H,
                item_kind="card",
                item_id=cid,
                name=name,
                description=display_desc,
                price=price,
                border_color=border_color,
                on_buy=self._on_buy_item,
            )
            self._items.append(item)
            self._widgets.append(item)

    # ── 数据查询 ──────────────────────────────────────────────────────────

    def _owned_relic_ids(self) -> List[str]:
        rs = getattr(self.game, "run_state", None)
        return rs.get_relic_ids() if rs else []

    def _gold(self) -> int:
        rs = getattr(self.game, "run_state", None)
        return rs.gold if rs else 0

    def _difficulty(self) -> int:
        rs = getattr(self.game, "run_state", None)
        return rs.difficulty if rs else 1

    # ── 购买逻辑 ──────────────────────────────────────────────────────────

    def _on_buy_item(self, item: _ShopItemWidget) -> None:
        rs = getattr(self.game, "run_state", None)
        if rs is None:
            return
        if not rs.can_afford(item.price):
            if self._info_label:
                self._info_label.text = "金币不足！"
                self._info_label.color = COLOR_DANGER
            return

        # 扣费
        rs.add_gold(-item.price)

        # 实际给予
        if item.item_kind == "relic":
            ok = rs.add_relic(item.item_id)
            msg = f"获得遗物 {item.item_id}" if ok else "购买遗物失败"
        else:
            rs.add_card(item.item_id)
            msg = f"获得卡牌 {item.item_id}"

        item.mark_sold()
        if self._info_label:
            self._info_label.text = msg
            self._info_label.color = COLOR_TEXT_SECONDARY

        self._refresh_gold_label()
        self._update_affordability()
        logger.info("购买: %s (%s) -%d G", item.item_id, item.item_kind, item.price)

    def _on_leave(self) -> None:
        logger.info("离开商店")
        self.game.state_machine.change(GameState.MAP_NAVIGATION, **self._return_kwargs)

    def _refresh_gold_label(self) -> None:
        if self._gold_label:
            self._gold_label.text = f"金币：{self._gold()} G"

    def _update_affordability(self) -> None:
        gold = self._gold()
        for item in self._items:
            item.set_affordable(gold >= item.price)

    # ── 事件 / 更新 / 渲染 ────────────────────────────────────────────────

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_leave()
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
