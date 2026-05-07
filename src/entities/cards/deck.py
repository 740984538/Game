"""
牌堆管理 - 对应开发计划 6-11
实现抽卡堆、弃牌堆、消耗堆的数据结构和洗牌逻辑。

职责:
  - 抽卡堆：从牌组抽到手中，抽完时洗牌弃牌堆
  - 弃牌堆：打出的卡进入弃牌堆
  - 消耗堆：消耗卡进入消耗堆（不可回收）
  - 洗牌逻辑
"""
from __future__ import annotations

import random
from typing import List, Optional

from src.entities.cards.card import Card


class Deck:
    """
    战斗中的牌堆管理器。

    管理三个牌堆:
      - draw_pile:    抽卡堆
      - discard_pile: 弃牌堆
      - exhaust_pile: 消耗堆 (不可回收)
      - hand:         当前手牌

    使用方式:
        deck = Deck(all_cards)
        deck.shuffle_draw_pile()
        drawn = deck.draw(5)  # 抽5张到手牌
    """

    def __init__(self, cards: Optional[List[Card]] = None) -> None:
        self.draw_pile: List[Card] = []
        self.hand: List[Card] = []
        self.discard_pile: List[Card] = []
        self.exhaust_pile: List[Card] = []

        if cards:
            # 初始化时所有卡进入抽卡堆
            self.draw_pile = [c.copy() for c in cards]

    # ─── 核心操作 ─────────────────────────────────────────────────────────

    def shuffle_draw_pile(self, seed: Optional[int] = None) -> None:
        """洗牌（抽卡堆）"""
        if seed is not None:
            rng = random.Random(seed)
            rng.shuffle(self.draw_pile)
        else:
            random.shuffle(self.draw_pile)

    def draw(self, count: int = 1) -> List[Card]:
        """
        从抽卡堆抽指定数量的卡到手牌。
        如果抽卡堆不足，先将弃牌堆洗入抽卡堆再继续抽。
        返回实际抽到的卡牌列表。
        """
        drawn: List[Card] = []
        for _ in range(count):
            # 抽卡堆为空时，将弃牌堆洗入
            if not self.draw_pile:
                if not self.discard_pile:
                    break  # 没有牌可抽
                self._reshuffle_discard_into_draw()

            if self.draw_pile:
                card = self.draw_pile.pop(0)
                self.hand.append(card)
                drawn.append(card)

        return drawn

    def play_card(self, card: Card) -> bool:
        """
        打出一张手牌。
        - 普通卡牌进入弃牌堆
        - 消耗型卡牌进入消耗堆
        返回 True 表示成功打出。
        """
        if card not in self.hand:
            return False

        self.hand.remove(card)

        if card.is_exhaust():
            self.exhaust_pile.append(card)
        else:
            self.discard_pile.append(card)

        return True

    def discard_hand(self) -> None:
        """回合结束时，将所有手牌放入弃牌堆"""
        self.discard_pile.extend(self.hand)
        self.hand.clear()

    def exhaust_card(self, card: Card) -> bool:
        """将指定卡牌消耗（从手牌移到消耗堆）"""
        if card in self.hand:
            self.hand.remove(card)
            self.exhaust_pile.append(card)
            return True
        return False

    def add_to_hand(self, card: Card) -> None:
        """直接添加卡牌到手牌（如通过效果生成的临时卡）"""
        self.hand.append(card)

    def add_to_draw_pile(self, card: Card, position: str = "random") -> None:
        """
        添加卡牌到抽卡堆。
        position: 'top' | 'bottom' | 'random'
        """
        if position == "top":
            self.draw_pile.insert(0, card)
        elif position == "bottom":
            self.draw_pile.append(card)
        else:
            idx = random.randint(0, len(self.draw_pile))
            self.draw_pile.insert(idx, card)

    def add_to_discard(self, card: Card) -> None:
        """添加卡牌到弃牌堆"""
        self.discard_pile.append(card)

    # ─── 查询 ─────────────────────────────────────────────────────────────

    @property
    def draw_count(self) -> int:
        """抽卡堆剩余数量"""
        return len(self.draw_pile)

    @property
    def discard_count(self) -> int:
        """弃牌堆数量"""
        return len(self.discard_pile)

    @property
    def exhaust_count(self) -> int:
        """消耗堆数量"""
        return len(self.exhaust_pile)

    @property
    def hand_count(self) -> int:
        """手牌数量"""
        return len(self.hand)

    @property
    def total_cards(self) -> int:
        """所有牌堆总卡牌数"""
        return (len(self.draw_pile) + len(self.hand) +
                len(self.discard_pile) + len(self.exhaust_pile))

    # ─── 内部方法 ─────────────────────────────────────────────────────────

    def _reshuffle_discard_into_draw(self) -> None:
        """将弃牌堆洗入抽卡堆"""
        self.draw_pile.extend(self.discard_pile)
        self.discard_pile.clear()
        self.shuffle_draw_pile()

    # ─── 重置 ─────────────────────────────────────────────────────────────

    def reset(self, cards: List[Card]) -> None:
        """重置牌堆（新战斗开始时）"""
        self.draw_pile = [c.copy() for c in cards]
        self.hand.clear()
        self.discard_pile.clear()
        self.exhaust_pile.clear()
        self.shuffle_draw_pile()

    def __repr__(self) -> str:
        return (f"Deck(draw={self.draw_count}, hand={self.hand_count}, "
                f"discard={self.discard_count}, exhaust={self.exhaust_count})")
