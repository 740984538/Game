"""
每日挑战种子系统
对应开发计划 §3-8（每日挑战种子系统）

功能：
- 基于日期（UTC）生成确定性随机种子
- 相同日期 + 相同角色 → 相同地图/敌人/掉落
- 每日挑战每天只能完成一次
- 每日挑战排行榜（本地存储）
"""
from __future__ import annotations

import hashlib
import json
import os
import logging
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from src.utils.constants import SAVE_DIR

logger = logging.getLogger(__name__)

_DAILY_FILE = os.path.join(SAVE_DIR, "daily_challenge.json")


# ── 数据结构 ──────────────────────────────────────────


@dataclass
class DailyRecord:
    """单次每日挑战记录"""
    date_str: str              # "YYYY-MM-DD"
    character_id: str = ""
    seed: int = 0
    score: int = 0             # 最终得分
    floor_reached: int = 0     # 到达层数
    completed: bool = False    # 是否通关
    played: bool = False       # 是否已参与（True = 今天已用掉机会）


@dataclass
class DailyLeaderboard:
    """本地每日挑战排行榜"""
    records: List[DailyRecord] = field(default_factory=list)


# ── 种子生成 ──────────────────────────────────────────


def get_today_str() -> str:
    """返回当天 UTC 日期字符串，格式 YYYY-MM-DD。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def generate_daily_seed(date_str: Optional[str] = None) -> int:
    """
    基于日期生成确定性种子。

    使用 SHA-256 哈希确保分布均匀。
    相同日期始终产生相同种子。

    Args:
        date_str: 日期字符串 "YYYY-MM-DD"，默认今天（UTC）。

    Returns:
        32 位无符号整数种子。
    """
    if date_str is None:
        date_str = get_today_str()
    raw = f"abyss-echo-daily-{date_str}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(h[:8], 16)  # 取前 8 位十六进制 → 32-bit seed


def generate_daily_seed_with_character(
    character_id: str,
    date_str: Optional[str] = None,
) -> int:
    """
    基于日期 + 角色 ID 生成确定性种子。

    保证：相同日期 + 相同角色 → 相同地图/敌人/掉落。
    不同角色在同一天会得到不同地图。

    Args:
        character_id: 角色 ID（如 "knight"）。
        date_str: 日期字符串，默认今天（UTC）。

    Returns:
        32 位无符号整数种子。
    """
    if date_str is None:
        date_str = get_today_str()
    raw = f"abyss-echo-daily-{date_str}-char-{character_id}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


# ── 每日挑战状态管理 ──────────────────────────────────


class DailyChallengeManager:
    """
    管理每日挑战的状态：是否已参与、排行榜读写。

    数据保存在 ``saves/daily_challenge.json``。
    """

    def __init__(self, save_path: str = _DAILY_FILE) -> None:
        self._save_path = save_path
        self._leaderboard = DailyLeaderboard()
        self._load()

    # ── 持久化 ────────────────────────────────────────

    def _load(self) -> None:
        """从 JSON 文件加载排行榜数据。"""
        if not os.path.isfile(self._save_path):
            return
        try:
            with open(self._save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records = []
            for rec in data.get("records", []):
                records.append(DailyRecord(**rec))
            self._leaderboard = DailyLeaderboard(records=records)
            logger.debug("加载每日挑战数据: %d 条记录", len(records))
        except Exception as e:
            logger.warning("加载每日挑战数据失败: %s", e)

    def _save(self) -> None:
        """将排行榜数据写入 JSON 文件。"""
        os.makedirs(os.path.dirname(self._save_path), exist_ok=True)
        try:
            data = {
                "records": [asdict(r) for r in self._leaderboard.records]
            }
            with open(self._save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("保存每日挑战数据成功")
        except Exception as e:
            logger.error("保存每日挑战数据失败: %s", e)

    # ── 查询 ──────────────────────────────────────────

    def has_played_today(self) -> bool:
        """当天是否已经参与过每日挑战。"""
        today = get_today_str()
        return any(
            r.date_str == today and r.played
            for r in self._leaderboard.records
        )

    def get_today_record(self) -> Optional[DailyRecord]:
        """获取当天的挑战记录（如果存在）。"""
        today = get_today_str()
        for r in self._leaderboard.records:
            if r.date_str == today:
                return r
        return None

    def get_leaderboard(self, limit: int = 30) -> List[DailyRecord]:
        """
        获取排行榜（按日期降序，最多 limit 条）。
        """
        sorted_records = sorted(
            self._leaderboard.records,
            key=lambda r: r.date_str,
            reverse=True,
        )
        return sorted_records[:limit]

    # ── 操作 ──────────────────────────────────────────

    def start_daily(self, character_id: str) -> DailyRecord:
        """
        开始今日挑战。

        如果今天已经玩过，抛出 ValueError。
        返回创建的 DailyRecord（seed 已填入）。
        """
        if self.has_played_today():
            raise ValueError("今日挑战已完成，每天只能参与一次")

        today = get_today_str()
        seed = generate_daily_seed_with_character(character_id, today)

        record = DailyRecord(
            date_str=today,
            character_id=character_id,
            seed=seed,
            played=True,
        )
        self._leaderboard.records.append(record)
        self._save()
        logger.info(
            "开始每日挑战: date=%s char=%s seed=%d",
            today, character_id, seed,
        )
        return record

    def finish_daily(
        self,
        score: int,
        floor_reached: int,
        completed: bool = False,
    ) -> None:
        """
        记录今日挑战结果。

        Args:
            score: 最终得分。
            floor_reached: 到达的层数。
            completed: 是否通关。
        """
        record = self.get_today_record()
        if record is None:
            logger.warning("finish_daily: 未找到今日记录")
            return

        record.score = score
        record.floor_reached = floor_reached
        record.completed = completed
        self._save()
        logger.info(
            "完成每日挑战: score=%d floor=%d completed=%s",
            score, floor_reached, completed,
        )

    def get_best_score(self) -> int:
        """获取历史最高得分。"""
        if not self._leaderboard.records:
            return 0
        return max(r.score for r in self._leaderboard.records)

    def get_streak(self) -> int:
        """
        计算连续参与天数（到今天为止的连续打卡天数）。
        """
        sorted_dates = sorted(
            set(r.date_str for r in self._leaderboard.records if r.played),
            reverse=True,
        )
        if not sorted_dates:
            return 0

        streak = 0
        expected = date.today()
        for d_str in sorted_dates:
            d = date.fromisoformat(d_str)
            if d == expected:
                streak += 1
                expected = date.fromordinal(expected.toordinal() - 1)
            else:
                break
        return streak
