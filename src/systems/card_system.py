"""
卡牌系统 - 对应开发计划:
  6-4: 手牌管理 (手牌区域点击选择、悬停放大)
  6-10: 卡牌升级逻辑 (卡牌升级机制)

对应文档 §5.3 卡牌/技能系统

职责:
  - 管理手牌区域的卡牌显示与交互
  - 处理卡牌选中、使用
  - 卡牌升级接口
"""
from __future__ import annotations

import logging
from typing import Callable, List, Optional, TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.entities.cards.card import Card
from src.entities.cards.deck import Deck
from src.ui.widgets.card_widget import CardWidget, CARD_WIDTH, CARD_HEIGHT
from src.utils.constants import SCREEN_WIDTH, SCREEN_HEIGHT

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# 手牌区域常量
HAND_AREA_Y = SCREEN_HEIGHT - 160  # 手牌区顶部Y
HAND_AREA_H = 160                   # 手牌区高度
HAND_CENTER_Y = HAND_AREA_Y + HAND_AREA_H - 20  # 卡牌底边Y
HAND_MAX_WIDTH = SCREEN_WIDTH - 200  # 手牌最大展开宽度
HAND_CENTER_X = SCREEN_WIDTH // 2    # 手牌中心X


class HandManager:
    """
    手牌管理器 (6-4)。

    职责:
    - 管理当前手牌的 CardWidget 列表
    - 处理鼠标悬停放大
    - 处理点击选中卡牌
    - 与 CombatManager 交互使用卡牌

    使用方式:
        hand_mgr = HandManager(on_card_click=self._on_card_selected)
        hand_mgr.update_hand(deck.hand)
        hand_mgr.handle_event(event)
        hand_mgr.render(surface)
    """

    def __init__(self, on_card_click: Optional[Callable] = None) -> None:
        self._card_widgets: List[CardWidget] = []
        self._selected_card: Optional[Card] = None
        self._on_card_click = on_card_click

    # ─── 属性 ─────────────────────────────────────────────────────────────

    @property
    def selected_card(self) -> Optional[Card]:
        return self._selected_card

    @property
    def card_count(self) -> int:
        return len(self._card_widgets)

    # ─── 手牌更新 ─────────────────────────────────────────────────────────

    def update_hand(self, cards: List[Card]) -> None:
        """
        根据当前手牌列表更新 CardWidget。
        每次 deck.hand 变化后调用。
        """
        self._card_widgets.clear()
        self._selected_card = None

        for i, card in enumerate(cards):
            widget = CardWidget(card, on_click=self._handle_card_click)
            self._card_widgets.append(widget)

        self._layout_cards()

    def _layout_cards(self) -> None:
        """布局手牌位置（等间距居中）"""
        count = len(self._card_widgets)
        if count == 0:
            return

        # 计算卡牌间距
        total_width = min(HAND_MAX_WIDTH, count * (CARD_WIDTH + 10))
        spacing = total_width / max(1, count)
        start_x = HAND_CENTER_X - total_width / 2 + spacing / 2

        for i, widget in enumerate(self._card_widgets):
            widget.x = start_x + i * spacing
            widget.y = HAND_CENTER_Y

    # ─── 交互处理 ─────────────────────────────────────────────────────────

    def handle_event(self, event) -> bool:
        """
        处理鼠标事件。
        返回 True 表示事件被消费。
        """
        if not _pygame_available:
            return False

        # 逆序处理（最上层的卡先响应）
        for widget in reversed(self._card_widgets):
            if widget.handle_event(event):
                return True

        # 点击空白区域取消选中
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._selected_card:
                # 检查是否点击在手牌区外
                mx, my = event.pos
                if my < HAND_AREA_Y - 30:
                    # 点击手牌区上方 = 使用卡牌（指定目标）
                    if self._on_card_click:
                        self._on_card_click(self._selected_card, event.pos)
                    self._deselect_all()
                    return True

        return False

    def _handle_card_click(self, card: Card) -> None:
        """卡牌被点击"""
        if self._selected_card == card:
            # 再次点击已选中的卡 = 取消选中
            self._deselect_all()
        else:
            # 选中新卡
            self._deselect_all()
            self._selected_card = card
            for widget in self._card_widgets:
                if widget.card == card:
                    widget.selected = True
                    break

    def _deselect_all(self) -> None:
        """取消所有选中"""
        self._selected_card = None
        for widget in self._card_widgets:
            widget.selected = False

    # ─── 更新 ─────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """每帧更新"""
        for widget in self._card_widgets:
            widget.update(dt)

    # ─── 渲染 ─────────────────────────────────────────────────────────────

    def render(self, surface) -> None:
        """渲染所有手牌"""
        if not _pygame_available:
            return

        # 先渲染未悬停的卡牌
        for widget in self._card_widgets:
            if not widget.hovered and widget.visible:
                widget.render(surface)

        # 再渲染悬停的卡牌（最上层）
        for widget in self._card_widgets:
            if widget.hovered and widget.visible:
                widget.render(surface)

    # ─── 清理 ─────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """清空手牌"""
        self._card_widgets.clear()
        self._selected_card = None


# ═══════════════════════════════════════════════════════════════════════════════
# 6-10: 卡牌升级管理
# ═══════════════════════════════════════════════════════════════════════════════

class CardUpgradeManager:
    """
    卡牌升级管理器 (6-10)。

    提供卡牌升级功能：
    - 检查卡牌是否可升级
    - 执行升级
    - 升级后名称显示 "+" 标记
    """

    @staticmethod
    def upgrade_card(card: Card) -> bool:
        """
        升级卡牌。
        - Card 数据结构包含 upgraded 布尔字段
        - 升级后属性变化（伤害+/费用-/额外效果）
        - 不可重复升级
        - 升级后卡牌名称显示 "+" 标记

        :return: True 升级成功, False 已满级
        """
        if not card.can_upgrade():
            return False
        return card.upgrade()

    @staticmethod
    def get_upgradable_cards(cards: List[Card]) -> List[Card]:
        """获取所有可升级的卡牌"""
        return [c for c in cards if c.can_upgrade()]


# ═══════════════════════════════════════════════════════════════════════════════
# ECS Processor 兼容
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import esper

    class CardProcessor(esper.Processor):
        """卡牌系统 ECS 处理器（保留接口，主逻辑由 HandManager 驱动）"""
        def process(self, dt: float) -> None:
            pass

except ImportError:
    class CardProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
