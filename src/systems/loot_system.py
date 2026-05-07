"""
掉落系统 - 对应开发计划 8-3 (遗物获取)，文档 §4.1.2 房间类型奖励

负责：
  - 监听 ``on_battle_win`` 事件
  - 根据房间类型（普通/精英/BOSS）按概率/确定性掉落遗物
  - 输出"奖励包"（金币 + 精华 + 遗物列表）供 CombatScene 使用

掉落规则（§4.1.2 / §5.2.2）：
  - 普通战斗：30% 概率掉落 1 个遗物（普通/稀有）
  - 精英战斗：100% 必掉 1 个遗物（最低稀有度=稀有）
  - BOSS 战斗：100% 掉落 3 选 1（最低稀有度=史诗）

调用方典型用法::

    loot_mgr = LootManager(config_loader, rng=random.Random(seed))
    reward = loot_mgr.roll_combat_reward("combat", floor_number=2)
    # reward = {
    #   "gold": 32,
    #   "essence": 0,
    #   "relic_choices": ["iron_will"],         # 直接获得
    #   "needs_selection": False,
    # }
    # 或
    # {
    #   "gold": 100, "essence": 3,
    #   "relic_choices": ["iron_will", "blood_rage", "fire_heart"],
    #   "needs_selection": True,                # 需要进入 RELIC_SELECT 场景
    # }
"""
from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional, TYPE_CHECKING

from src.core.event_manager import event_manager
from src.generation.loot_generator import LootGenerator

if TYPE_CHECKING:
    from src.data.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 掉落配置（与 §4.1.2 / §5.2.2 对齐）
# ═══════════════════════════════════════════════════════════════════════════════

# 普通战斗掉落概率
_NORMAL_RELIC_DROP_CHANCE: float = 0.30

# 各房间类型最低稀有度
_MIN_RARITY_BY_ROOM: Dict[str, str] = {
    "combat": "common",
    "elite":  "rare",
    "boss":   "epic",
}

# 各房间类型遗物候选数量（=1 直接获得；>1 进入选择场景）
_RELIC_CHOICES_BY_ROOM: Dict[str, int] = {
    "combat": 1,
    "elite":  1,
    "boss":   3,
}

# 金币掉落区间（按楼层基础值）
_BASE_GOLD_BY_ROOM: Dict[str, tuple] = {
    "combat": (10, 25),
    "elite":  (40, 60),
    "boss":   (80, 150),
}

# 灵魂精华掉落
_ESSENCE_BY_ROOM: Dict[str, int] = {
    "combat": 0,
    "elite":  1,
    "boss":   3,
}


# ═══════════════════════════════════════════════════════════════════════════════
# LootManager - 高层 API
# ═══════════════════════════════════════════════════════════════════════════════

class LootManager:
    """
    战利品管理器，负责按房间类型生成奖励包并通过事件总线对外通知。

    构造时即注册 ``on_battle_win`` 监听器；调用方也可主动调用
    :py:meth:`roll_combat_reward` 直接生成奖励而不等待事件。
    """

    def __init__(self,
                 config_loader: Optional["ConfigLoader"] = None,
                 rng: Optional[random.Random] = None,
                 relic_pool: Optional[Dict[str, dict]] = None) -> None:
        if config_loader is None and relic_pool is None:
            from src.data.config_loader import ConfigLoader
            config_loader = ConfigLoader()

        if relic_pool is None:
            relic_pool = config_loader.load_relics()

        self._rng = rng or random.Random()
        self._relic_pool: Dict[str, dict] = relic_pool
        self._loot_gen = LootGenerator(self._rng, relic_pool)

        # 上下文（供事件回调读取楼层与房间信息）
        self._current_floor: int = 1
        self._current_room: str = "combat"

        # 事件订阅
        event_manager.subscribe("on_battle_win", self._on_battle_win)
        event_manager.subscribe("on_floor_start", self._on_floor_start)

    # ── 上下文 ────────────────────────────────────────────────────────────

    def set_context(self, floor_number: int, room_type: str) -> None:
        """战斗开始时由 CombatScene 调用，记录当前房间信息"""
        self._current_floor = max(1, int(floor_number))
        self._current_room = self._normalize_room(room_type)

    # ── 主入口 ────────────────────────────────────────────────────────────

    def roll_combat_reward(self, room_type: str,
                           floor_number: int = 1,
                           extra_relic_choices: int = 0) -> dict:
        """
        生成一次战斗奖励包。

        :param room_type:       "combat" / "elite" / "boss"
        :param floor_number:    当前楼层（影响金币）
        :param extra_relic_choices: 来自遗物（如幸运四叶草）的额外候选
        :return: 奖励字典
        """
        room = self._normalize_room(room_type)
        gold = self._roll_gold(room, floor_number)
        essence = _ESSENCE_BY_ROOM.get(room, 0)

        relic_choices = self._roll_relics(room, extra_relic_choices)

        # 普通战斗按概率决定是否掉落
        if room == "combat" and self._rng.random() > _NORMAL_RELIC_DROP_CHANCE:
            relic_choices = []

        needs_selection = len(relic_choices) > 1

        reward = {
            "room_type": room,
            "floor_number": floor_number,
            "gold": gold,
            "essence": essence,
            "relic_choices": relic_choices,
            "needs_selection": needs_selection,
        }

        logger.info(
            "战利品生成: room=%s floor=%d gold=%d relics=%s",
            room, floor_number, gold, relic_choices,
        )
        event_manager.publish("on_loot_generated", reward=reward)
        return reward

    # ── 内部 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_room(room_type) -> str:
        """将 RoomType 枚举或字符串转换为底层字符串"""
        if room_type is None:
            return "combat"
        if hasattr(room_type, "value"):
            return str(room_type.value)
        return str(room_type)

    def _roll_gold(self, room: str, floor_number: int) -> int:
        lo, hi = _BASE_GOLD_BY_ROOM.get(room, (10, 20))
        # 楼层难度系数：每升一层金币 +10%
        scale = 1.0 + 0.10 * (floor_number - 1)
        return int(self._rng.randint(lo, hi) * scale)

    def _roll_relics(self, room: str, extra: int) -> List[str]:
        if not self._relic_pool:
            return []
        n = _RELIC_CHOICES_BY_ROOM.get(room, 0) + max(0, extra)
        if n <= 0:
            return []
        min_rarity = _MIN_RARITY_BY_ROOM.get(room, "common")
        if n == 1:
            return [self._loot_gen.roll_relic(min_rarity)]
        return self._loot_gen.roll_n_relics(n, min_rarity)

    # ── 事件回调 ──────────────────────────────────────────────────────────

    def _on_battle_win(self, **kwargs) -> None:
        """on_battle_win 事件触发：生成奖励包（不直接发放，由场景决定流程）"""
        room = kwargs.get("room_type", self._current_room)
        floor = kwargs.get("floor_number", self._current_floor)
        extra = kwargs.get("extra_relic_choices", 0)
        self.roll_combat_reward(room, floor, extra)

    def _on_floor_start(self, **kwargs) -> None:
        """更新楼层缓存"""
        floor = kwargs.get("floor_number")
        if floor is not None:
            self._current_floor = int(floor)


# ═══════════════════════════════════════════════════════════════════════════════
# ECS Processor 兼容（保留原有占位）
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import esper

    class LootProcessor(esper.Processor):
        """
        ECS 战利品处理器（保留以兼容已有注册）。
        实际逻辑由 LootManager + 事件总线驱动。
        """
        def process(self, dt: float) -> None:
            pass

except ImportError:
    class LootProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
