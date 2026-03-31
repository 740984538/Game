"""
数据模型定义 - 对应文档 §8.2.1 存档结构
使用 dataclass 定义存档相关的数据结构
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional


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
    # 图鉴数据
    seen_relics: List[str] = field(default_factory=list)
    seen_enemies: List[str] = field(default_factory=list)
    seen_events: List[str] = field(default_factory=list)


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
    player: PlayerRunState = field(default_factory=PlayerRunState)
    map_state: dict = field(default_factory=dict)   # 已访问节点等
    run_stats: dict = field(default_factory=dict)   # 击杀数、伤害等统计
    is_active: bool = True


@dataclass
class GameSaveData:
    """完整存档文件结构"""
    meta_progress: MetaProgress = field(default_factory=MetaProgress)
    current_run: Optional[RunState] = None
    save_version: str = "1.0"
