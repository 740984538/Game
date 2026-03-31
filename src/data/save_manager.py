"""
存档管理器 - 对应文档 §10.4.2 / §7.1 存档系统
负责元进度和当局进度的序列化/反序列化
"""
from __future__ import annotations
import pickle
from typing import Optional

from src.data.database import Database
from src.data.models import MetaProgress, RunState, GameSaveData


class SaveManager:
    """
    存档管理器，使用 pickle 序列化数据类，SQLite 持久化。
    对应文档 §7.1.1 存档类型：
    - 元进度存档：实时保存
    - 当局存档：在特定节点（休息点/关卡结束）保存
    """

    def __init__(self, db_path: str = "saves/game.db") -> None:
        self.db = Database(db_path)

    # ── 元进度 ─────────────────────────────────────

    def save_meta_progress(self, progress: MetaProgress) -> None:
        """保存元进度（§7.1.1 元进度存档，实时保存）"""
        data = pickle.dumps(progress)
        self.db.upsert_blob("meta_progress", "id", 1, "data", data)

    def load_meta_progress(self) -> MetaProgress:
        """加载元进度，若不存在则返回初始状态"""
        blob = self.db.fetch_blob("meta_progress", "id", 1)
        if blob:
            return pickle.loads(blob)
        return MetaProgress()

    # ── 当局进度 ───────────────────────────────────

    def save_run_state(self, run_state: RunState, slot: int = 0) -> None:
        """
        保存当局进度（§7.1.2 存档规则：仅普通难度以下可手动存档）
        对应文档：不允许在困难及以上难度随时存档
        """
        data = pickle.dumps(run_state)
        self.db.upsert_blob("run_saves", "slot", slot, "data", data)

    def load_run_state(self, slot: int = 0) -> Optional[RunState]:
        """加载当局进度，不存在则返回 None"""
        blob = self.db.fetch_blob("run_saves", "slot", slot)
        if blob:
            return pickle.loads(blob)
        return None

    def delete_run_state(self, slot: int = 0) -> None:
        """删除当局存档（死亡或通关后）"""
        self.db.conn.execute("DELETE FROM run_saves WHERE slot = ?", (slot,))
        self.db.conn.commit()

    # ── 设置 ───────────────────────────────────────

    def save_setting(self, key: str, value: str) -> None:
        self.db.set_setting(key, value)

    def load_setting(self, key: str, default: str = "") -> str:
        return self.db.get_setting(key, default)

    def close(self) -> None:
        self.db.close()
