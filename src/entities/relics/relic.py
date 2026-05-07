"""
遗物注册表与导出 - 对应开发计划 8-2 (遗物配置读取)，文档 §5.2

提供：
  - Relic / RelicEffect / RelicManager 的统一导出
  - RelicRegistry 单例：读取 config/relics/ 下的全部 YAML 并构造 Relic 对象，
    供战斗系统、商店、奖励等模块按 id 查询。

典型用法::

    registry = RelicRegistry.instance()
    registry.load_all()                       # 从 config/relics/ 加载
    relic = registry.get("iron_will")
    commons = registry.filter_by_rarity("common")
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from src.entities.relics.relic_manager import Relic, RelicEffect, RelicManager
from src.utils.enums import Rarity

logger = logging.getLogger(__name__)

__all__ = ["Relic", "RelicEffect", "RelicManager", "RelicRegistry"]


class RelicRegistry:
    """
    全局遗物注册表（单例），统一管理从 YAML 加载的所有 Relic 数据。

    数据源：``config/relics/*.yaml``
    """

    _instance: Optional["RelicRegistry"] = None

    @classmethod
    def instance(cls) -> "RelicRegistry":
        if cls._instance is None:
            inst = cls.__new__(cls)
            inst._relics = {}        # type: Dict[str, Relic]
            inst._raw = {}           # type: Dict[str, dict]
            inst._loaded = False
            cls._instance = inst
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（主要用于测试）"""
        cls._instance = None

    # ── 加载 ──────────────────────────────────────────────────────────────

    def load_all(self, config_dir: str = "config") -> None:
        """
        从 ``config/relics/`` 目录加载所有 YAML 遗物配置。
        重复调用会重新加载。
        """
        from src.data.config_loader import ConfigLoader
        loader = ConfigLoader(config_dir)
        loader.clear_cache()  # 确保拿到最新数据
        raw_pool = loader.load_relics()
        self._raw = dict(raw_pool)
        self._relics = {
            rid: Relic(rid, cfg) for rid, cfg in raw_pool.items()
        }
        self._loaded = True
        logger.info("RelicRegistry 加载完成: %d 个遗物", len(self._relics))

    def load_from_pool(self, relic_pool: Dict[str, dict]) -> None:
        """直接从已加载的字典构建（测试或缓存场景）"""
        self._raw = dict(relic_pool)
        self._relics = {
            rid: Relic(rid, cfg) for rid, cfg in relic_pool.items()
        }
        self._loaded = True

    # ── 查询 ──────────────────────────────────────────────────────────────

    def get(self, relic_id: str) -> Optional[Relic]:
        """按 id 获取遗物，不存在返回 None"""
        return self._relics.get(relic_id)

    def get_raw(self, relic_id: str) -> Optional[dict]:
        """按 id 获取原始 YAML 字典（供 RelicManager 复用）"""
        return self._raw.get(relic_id)

    def all_relics(self) -> List[Relic]:
        """返回所有遗物对象，按 id 排序"""
        return sorted(self._relics.values(), key=lambda r: r.id)

    def all_ids(self) -> List[str]:
        return sorted(self._relics.keys())

    def filter_by_rarity(self, rarity) -> List[Relic]:
        """
        按稀有度筛选。

        :param rarity: 字符串（"common"/"rare"/"epic"/"legendary"）或 Rarity 枚举
        """
        target = rarity.value if isinstance(rarity, Rarity) else str(rarity)
        return [r for r in self._relics.values() if r.rarity == target]

    def raw_pool(self) -> Dict[str, dict]:
        """返回完整原始配置字典（供 LootGenerator / RelicManager 使用）"""
        return dict(self._raw)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def __len__(self) -> int:
        return len(self._relics)

    def __contains__(self, relic_id: str) -> bool:
        return relic_id in self._relics
