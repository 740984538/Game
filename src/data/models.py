"""
数据模型定义 - 对应文档 §8.2.1 存档结构
使用 dataclass 定义存档相关的数据结构

阶段 9-1：完善存档数据结构
- MetaProgress：跨局元进度（灵魂碎片 / 解锁 / 图鉴）
- PlayerRunState：单局玩家快照
- RunState：当局存档
- GameSaveData：顶层存档容器
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# 当前存档结构版本，反序列化时 SaveManager 会用此值校验/迁移
SAVE_VERSION = "1.1"


@dataclass
class MetaProgress:
    """
    元进度数据（跨局保留）
    对应文档 §3.3.1 元进度系统 / §8.2.1 meta_progress 节
    """
    soul_shards: int = 0
    unlocked_characters: List[str] = field(default_factory=lambda: ["knight"])
    unlocked_relics: List[str] = field(default_factory=list)
    unlocked_difficulties: List[int] = field(default_factory=lambda: [0, 1])
    achievements: List[str] = field(default_factory=list)
    best_runs: List[dict] = field(default_factory=list)
    story_fragments: List[str] = field(default_factory=list)
    # 图鉴数据 - 阶段 9-10
    seen_relics: List[str] = field(default_factory=list)
    seen_enemies: List[str] = field(default_factory=list)
    seen_events: List[str] = field(default_factory=list)
    seen_cards: List[str] = field(default_factory=list)
    # 局外永久强化（key -> 等级），阶段 9-4 使用
    perm_upgrades: Dict[str, int] = field(default_factory=dict)
    # 累计统计（仅用于成就/展示，跨局递增）
    total_runs: int = 0
    total_victories: int = 0

    # ── 图鉴辅助 ──────────────────────────────────────
    def see_relic(self, relic_id: str) -> bool:
        if relic_id and relic_id not in self.seen_relics:
            self.seen_relics.append(relic_id)
            return True
        return False

    def see_card(self, card_id: str) -> bool:
        if card_id and card_id not in self.seen_cards:
            self.seen_cards.append(card_id)
            return True
        return False

    def see_enemy(self, enemy_id: str) -> bool:
        if enemy_id and enemy_id not in self.seen_enemies:
            self.seen_enemies.append(enemy_id)
            return True
        return False

    def unlock_character(self, char_id: str) -> bool:
        if char_id and char_id not in self.unlocked_characters:
            self.unlocked_characters.append(char_id)
            return True
        return False


@dataclass
class PlayerRunState:
    """单局玩家状态快照"""
    character_id: str = "knight"
    health: int = 80
    max_health: int = 80
    gold: int = 100
    essence: int = 0
    relics: List[str] = field(default_factory=list)
    cards: List[str] = field(default_factory=list)
    stats_override: Dict[str, float] = field(default_factory=dict)


@dataclass
class RunState:
    """
    当局存档数据
    对应文档 §8.2.1 current_run 节
    """
    seed: int = 0
    floor: int = 1
    difficulty: int = 1
    daily: bool = False
    player: PlayerRunState = field(default_factory=PlayerRunState)
    map_state: dict = field(default_factory=dict)   # 已访问节点等
    run_stats: dict = field(default_factory=dict)   # 击杀数、伤害等统计
    is_active: bool = True


@dataclass
class GameSaveData:
    """完整存档文件结构"""
    meta_progress: MetaProgress = field(default_factory=MetaProgress)
    current_run: Optional[RunState] = None
    save_version: str = SAVE_VERSION
