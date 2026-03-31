"""
Build 构筑管理器 - 对应文档 §2.1.1 核心机制（遗物Build构筑）
跟踪玩家当前 Build 的遗物、卡牌组合并计算协同效果
"""
from __future__ import annotations
from typing import List


class BuildManager:
    """管理玩家当局的 Build（遗物+卡牌组合）"""

    def __init__(self) -> None:
        self.relic_ids: List[str] = []
        self.card_ids: List[str] = []

    def add_relic(self, relic_id: str) -> None:
        if relic_id not in self.relic_ids:
            self.relic_ids.append(relic_id)

    def add_card(self, card_id: str) -> None:
        self.card_ids.append(card_id)

    def remove_card(self, card_id: str) -> None:
        if card_id in self.card_ids:
            self.card_ids.remove(card_id)

    def get_summary(self) -> dict:
        return {
            "relics": list(self.relic_ids),
            "cards": list(self.card_ids),
            "relic_count": len(self.relic_ids),
            "card_count": len(self.card_ids),
        }

    def reset(self) -> None:
        self.relic_ids.clear()
        self.card_ids.clear()
