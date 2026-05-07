"""
存档管理器 - 对应文档 §10.4.2 / §7.1 存档系统
负责元进度和当局进度的序列化/反序列化

阶段 9-2 / 9-3 / 9-5：
- SaveManager 单例：游戏全局共享一份 SQLite 连接
- has_run_state(): 用于 MainMenu 判断是否显示「继续游戏」
- save_setting / load_setting：透传 Database 用于阶段 9-5 设置持久化
"""
from __future__ import annotations
import logging
import pickle
from typing import Optional

from src.data.database import Database
from src.data.models import MetaProgress, RunState, GameSaveData, SAVE_VERSION

logger = logging.getLogger(__name__)


class SaveManager:
    """
    存档管理器，使用 pickle 序列化数据类，SQLite 持久化。
    对应文档 §7.1.1 存档类型：
    - 元进度存档：实时保存
    - 当局存档：在特定节点（休息点/关卡结束）保存
    """

    _instance: Optional["SaveManager"] = None
    _instance_path: Optional[str] = None

    # ── 单例访问 ───────────────────────────────────

    @classmethod
    def instance(cls, db_path: str = "saves/game.db") -> "SaveManager":
        """
        获取全局单例。第一次调用时按 *db_path* 创建，
        后续如传入不同路径会重置实例（主要给单元测试使用）。
        """
        if cls._instance is None or cls._instance_path != db_path:
            if cls._instance is not None:
                try:
                    cls._instance.close()
                except Exception:
                    pass
            cls._instance = cls(db_path)
            cls._instance_path = db_path
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（测试用）"""
        if cls._instance is not None:
            try:
                cls._instance.close()
            except Exception:
                pass
        cls._instance = None
        cls._instance_path = None

    def __init__(self, db_path: str = "saves/game.db") -> None:
        self.db = Database(db_path)
        self._meta_cache: Optional[MetaProgress] = None

    # ── 元进度 ─────────────────────────────────────

    def save_meta_progress(self, progress: MetaProgress) -> None:
        """保存元进度（§7.1.1 元进度存档，实时保存）"""
        data = pickle.dumps(progress)
        self.db.upsert_blob("meta_progress", "id", 1, "data", data)
        self._meta_cache = progress

    def load_meta_progress(self) -> MetaProgress:
        """加载元进度，若不存在则返回初始状态"""
        if self._meta_cache is not None:
            return self._meta_cache
        blob = self.db.fetch_blob("meta_progress", "id", 1)
        if blob:
            try:
                meta = pickle.loads(blob)
                # 兼容旧版本：补齐缺失字段
                meta = self._migrate_meta(meta)
                self._meta_cache = meta
                return meta
            except Exception as exc:
                logger.warning("元进度反序列化失败 %s，重置为初始状态", exc)
        self._meta_cache = MetaProgress()
        return self._meta_cache

    def _migrate_meta(self, meta: MetaProgress) -> MetaProgress:
        """补齐 9-1 新增字段（旧存档兼容）"""
        for attr, default in (
            ("seen_cards", []),
            ("perm_upgrades", {}),
            ("total_runs", 0),
            ("total_victories", 0),
        ):
            if not hasattr(meta, attr) or getattr(meta, attr) is None:
                setattr(meta, attr, default if not callable(default) else default())
        return meta

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
            try:
                return pickle.loads(blob)
            except Exception as exc:
                logger.warning("当局存档反序列化失败 %s，删除该存档", exc)
                self.delete_run_state(slot)
        return None

    def delete_run_state(self, slot: int = 0) -> None:
        """删除当局存档（死亡或通关后）"""
        self.db.conn.execute("DELETE FROM run_saves WHERE slot = ?", (slot,))
        self.db.conn.commit()

    def has_run_state(self, slot: int = 0) -> bool:
        """是否存在可继续的当局存档（用于主菜单显示『继续游戏』）"""
        row = self.db.conn.execute(
            "SELECT 1 FROM run_saves WHERE slot = ?", (slot,)
        ).fetchone()
        return row is not None

    # ── 设置 ───────────────────────────────────────

    def save_setting(self, key: str, value: str) -> None:
        self.db.set_setting(key, value)

    def load_setting(self, key: str, default: str = "") -> str:
        return self.db.get_setting(key, default)

    # ── 元进度便捷接口（阶段 9-3） ─────────────────

    def add_soul_shards(self, amount: int) -> int:
        """
        给元进度增加灵魂碎片（GameOver / Victory 调用）。
        返回累加后的总数。
        """
        meta = self.load_meta_progress()
        meta.soul_shards = max(0, meta.soul_shards + int(amount))
        self.save_meta_progress(meta)
        return meta.soul_shards

    def spend_soul_shards(self, amount: int) -> bool:
        """扣除灵魂碎片。不足时返回 False 不做修改。"""
        meta = self.load_meta_progress()
        if meta.soul_shards < amount:
            return False
        meta.soul_shards -= int(amount)
        self.save_meta_progress(meta)
        return True

    def record_run_finished(self, victory: bool) -> None:
        """战局结算时累加 total_runs / total_victories。"""
        meta = self.load_meta_progress()
        meta.total_runs = int(getattr(meta, "total_runs", 0)) + 1
        if victory:
            meta.total_victories = int(getattr(meta, "total_victories", 0)) + 1
        self.save_meta_progress(meta)

    def close(self) -> None:
        self.db.close()
        self._meta_cache = None

    @property
    def save_version(self) -> str:
        return SAVE_VERSION
