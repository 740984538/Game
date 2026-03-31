"""
数据库操作封装 - 对应文档 §10.1 SQLite
对 sqlite3 的简单包装，提供统一的查询/写入接口
"""
from __future__ import annotations
import sqlite3
import os
from pathlib import Path


class Database:
    """SQLite 数据库操作类"""

    def __init__(self, db_path: str = "saves/game.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        """初始化数据库表结构"""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS meta_progress (
                id      INTEGER PRIMARY KEY,
                data    BLOB NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS run_saves (
                slot    INTEGER PRIMARY KEY,
                data    BLOB NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS settings (
                key     TEXT PRIMARY KEY,
                value   TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def upsert_blob(self, table: str, id_col: str, id_val, data_col: str, data: bytes) -> None:
        self.conn.execute(
            f"INSERT OR REPLACE INTO {table} ({id_col}, {data_col}) VALUES (?, ?)",
            (id_val, data)
        )
        self.conn.commit()

    def fetch_blob(self, table: str, id_col: str, id_val) -> bytes | None:
        row = self.conn.execute(
            f"SELECT data FROM {table} WHERE {id_col} = ?", (id_val,)
        ).fetchone()
        return row["data"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        self.conn.commit()

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def close(self) -> None:
        self.conn.close()
