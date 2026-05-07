"""
RunState 管理器 - 阶段 8 共享玩家状态

为各场景（Shop / Rest / Event / Combat / Pause / GameOver / Victory）
提供贯穿整局的玩家状态访问入口。

不依赖 ECS：跨房间的 HP / 金币 / 卡组 / 遗物 / 统计在此持久化，
进入战斗时由 CombatScene 同步到 ECS Player 实体，战斗结束后再同步回来。

典型用法::

    # 主菜单 / 角色选择确认时
    self.game.run_state.start_new_run("knight", seed=12345, daily=False)

    # 任意场景
    self.game.run_state.gold += 50
    self.game.run_state.relic_manager.add_relic("iron_will")

    # 战斗结束
    self.game.run_state.record_combat_result(victory=True, kills=3)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.entities.relics.relic import RelicRegistry
from src.entities.relics.relic_manager import RelicManager
from src.entities.player.character_stats import (
    CharacterRegistry, build_initial_run_stats,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 统计数据（用于 GameOver / Victory 展示）
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RunStatistics:
    """整局战斗统计数据"""
    floors_cleared: int = 0
    rooms_cleared: int = 0
    combats_won: int = 0
    elite_kills: int = 0
    bosses_killed: int = 0
    total_kills: int = 0
    total_damage_dealt: int = 0
    total_damage_taken: int = 0
    cards_played: int = 0
    relics_collected: int = 0
    gold_earned: int = 0
    play_seconds: float = 0.0
    last_killed_by: str = ""           # 玩家死亡时记录死因


# ═══════════════════════════════════════════════════════════════════════════════
# 主 RunState 管理器
# ═══════════════════════════════════════════════════════════════════════════════

class RunStateManager:
    """
    跨场景玩家状态容器。

    在 Game 初始化时挂载在 ``Game.run_state`` 上，所有场景通过
    ``self.game.run_state`` 访问。
    """

    def __init__(self) -> None:
        # 角色 / 种子
        self.character_id: str = ""
        self.seed: int = 0
        self.daily: bool = False
        self.difficulty: int = 1            # 0=新手, 1=普通, 2=困难, ...
        self.active: bool = False           # 是否有进行中的局

        # 进度
        self.current_floor: int = 1

        # 玩家数值
        self.health: int = 80
        self.max_health: int = 80
        self.gold: int = 100
        self.essence: int = 0

        # 卡组（card_id 列表）
        self.deck: List[str] = []

        # 遗物管理器（懒加载，依赖 RelicRegistry）
        self.relic_manager: Optional[RelicManager] = None

        # 统计
        self.stats: RunStatistics = RunStatistics()

        # 战斗结果缓存（供 GameOver / Victory / RelicSelect 使用）
        self.last_battle: Dict[str, Any] = {}

    # ── 整局生命周期 ────────────────────────────────────────────────────

    def start_new_run(self, character_id: str,
                      seed: int = 0,
                      daily: bool = False,
                      difficulty: int = 1) -> None:
        """
        开始新一局。
        从角色配置初始化 HP / 金币 / 卡组 / 起始遗物。
        """
        self.character_id = character_id
        self.seed = seed
        self.daily = daily
        self.difficulty = difficulty
        self.current_floor = 1
        self.stats = RunStatistics()
        self.last_battle = {}

        # 加载角色
        registry = CharacterRegistry.instance()
        if not registry.is_loaded:
            registry.load_all()
        char = registry.get(character_id)

        if char is None:
            logger.warning("未找到角色 %s, 使用默认值", character_id)
            self.health = 80
            self.max_health = 80
            self.gold = 100
            self.deck = []
            starting_relic = ""
        else:
            init_stats = build_initial_run_stats(char)
            self.health = init_stats["health"]
            self.max_health = init_stats["max_health"]
            self.gold = char.starting_gold
            self.deck = list(char.starting_deck)
            starting_relic = char.starting_relic or ""

        # 遗物管理器
        self._init_relic_manager()
        if starting_relic:
            self.relic_manager.add_relic(starting_relic)
            self.stats.relics_collected = len(self.relic_manager)

        self.essence = 0
        self.active = True
        logger.info(
            "开始新局: char=%s, hp=%d/%d, gold=%d, relics=%s",
            character_id, self.health, self.max_health, self.gold,
            self.relic_manager.get_relic_ids(),
        )

    def end_run(self) -> None:
        """结束当前局，清空状态（保留 stats 供结算场景读取）"""
        self.active = False

    def is_alive(self) -> bool:
        return self.active and self.health > 0

    # ── 状态修改 ────────────────────────────────────────────────────────

    def take_damage(self, amount: int) -> int:
        """扣血，返回实际承受伤害（受 max_health 下限保护）"""
        amount = max(0, int(amount))
        old = self.health
        self.health = max(0, self.health - amount)
        actual = old - self.health
        self.stats.total_damage_taken += actual
        return actual

    def heal(self, amount: int) -> int:
        """治疗，返回实际恢复量"""
        amount = max(0, int(amount))
        old = self.health
        self.health = min(self.max_health, self.health + amount)
        return self.health - old

    def add_max_health(self, amount: int) -> None:
        """增加最大生命值上限并同步当前 HP"""
        delta = int(amount)
        self.max_health = max(1, self.max_health + delta)
        if delta > 0:
            self.health += delta
        else:
            self.health = min(self.health, self.max_health)

    def add_gold(self, amount: int) -> int:
        """增加/扣除金币（不会变成负数），返回最终金币"""
        from src.utils.constants import GOLD_CAP
        self.gold = max(0, min(GOLD_CAP, self.gold + int(amount)))
        if amount > 0:
            self.stats.gold_earned += int(amount)
        return self.gold

    def can_afford(self, cost: int) -> bool:
        return self.gold >= max(0, int(cost))

    def add_essence(self, amount: int) -> int:
        from src.utils.constants import ESSENCE_CAP
        self.essence = max(0, min(ESSENCE_CAP, self.essence + int(amount)))
        return self.essence

    def add_card(self, card_id: str) -> None:
        if card_id:
            self.deck.append(card_id)

    def remove_card(self, card_id: str) -> bool:
        if card_id in self.deck:
            self.deck.remove(card_id)
            return True
        return False

    def add_relic(self, relic_id: str) -> bool:
        """通过遗物管理器添加遗物，自动应用 on_pickup"""
        if not self.relic_manager:
            self._init_relic_manager()
        added = self.relic_manager.add_relic(relic_id)
        if added is not None:
            # 应用 on_pickup 副作用
            ctx = self.relic_manager.latest_context
            self._apply_pickup_effects(ctx)
            self.stats.relics_collected = len(self.relic_manager)
            return True
        return False

    def has_relic(self, relic_id: str) -> bool:
        return bool(self.relic_manager and self.relic_manager.has_relic(relic_id))

    def get_relic_ids(self) -> List[str]:
        return self.relic_manager.get_relic_ids() if self.relic_manager else []

    # ── 楼层切换 ────────────────────────────────────────────────────────

    def advance_floor(self) -> int:
        """进入下一层。返回新层号。"""
        self.current_floor += 1
        self.stats.floors_cleared += 1
        return self.current_floor

    # ── 战斗结果 ────────────────────────────────────────────────────────

    def record_combat_result(self, victory: bool,
                             room_type: str = "combat",
                             kills: int = 0,
                             damage_dealt: int = 0,
                             damage_taken: int = 0,
                             cards_played: int = 0,
                             killed_by: str = "") -> None:
        """战斗结束时累加统计"""
        self.last_battle = {
            "victory": victory,
            "room_type": room_type,
            "kills": kills,
            "damage_dealt": damage_dealt,
            "damage_taken": damage_taken,
            "cards_played": cards_played,
            "killed_by": killed_by,
        }
        self.stats.total_kills += kills
        self.stats.total_damage_dealt += damage_dealt
        # take_damage 已在 take_damage() 累加，避免重复
        self.stats.cards_played += cards_played

        if victory:
            self.stats.combats_won += 1
            self.stats.rooms_cleared += 1
            if room_type == "elite":
                self.stats.elite_kills += 1
            elif room_type == "boss":
                self.stats.bosses_killed += 1
        else:
            self.stats.last_killed_by = killed_by

    # ── 内部 ────────────────────────────────────────────────────────────

    def _init_relic_manager(self) -> None:
        registry = RelicRegistry.instance()
        if not registry.is_loaded:
            try:
                registry.load_all()
            except Exception as exc:
                logger.warning("加载遗物注册表失败: %s", exc)
        pool = registry.raw_pool() if registry.is_loaded else {}
        self.relic_manager = RelicManager(pool)

    def _apply_pickup_effects(self, ctx: Dict[str, Any]) -> None:
        """将遗物 on_pickup 后写入 context 的被动加成应用到玩家数值"""
        bonus_hp = ctx.get("max_health_bonus", 0)
        if bonus_hp:
            self.add_max_health(bonus_hp)
        # 其他被动加成（attack_bonus 等）由战斗系统在初始化时读取 build_initial_run_stats

    # ── 序列化 ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "seed": self.seed,
            "daily": self.daily,
            "difficulty": self.difficulty,
            "current_floor": self.current_floor,
            "health": self.health,
            "max_health": self.max_health,
            "gold": self.gold,
            "essence": self.essence,
            "deck": list(self.deck),
            "relics": self.get_relic_ids(),
            "stats": self.stats.__dict__,
            "active": self.active,
        }

    # ── 与持久化模型互转（阶段 9-2 当局存档） ─────────────────────────

    def to_run_state_model(self):
        """
        将 RunStateManager 转为可序列化的 :class:`src.data.models.RunState`。

        用于阶段 9-2 自动存档：在战斗结束 / 离开重要节点时调用，
        将得到的 RunState 喂给 :class:`SaveManager.save_run_state`。
        """
        from src.data.models import RunState, PlayerRunState
        player = PlayerRunState(
            character_id=self.character_id,
            health=self.health,
            max_health=self.max_health,
            gold=self.gold,
            essence=self.essence,
            relics=self.get_relic_ids(),
            cards=list(self.deck),
        )
        return RunState(
            seed=self.seed,
            floor=self.current_floor,
            difficulty=self.difficulty,
            daily=self.daily,
            player=player,
            map_state={},
            run_stats=dict(self.stats.__dict__),
            is_active=self.active,
        )

    def restore_from_run_state_model(self, model) -> None:
        """
        从 :class:`src.data.models.RunState` 恢复 RunStateManager 状态（阶段 9-2 继续游戏）。
        会重新初始化遗物管理器并把存档中的遗物逐个加入。
        """
        if model is None:
            return
        player = model.player
        self.character_id = player.character_id
        self.seed = model.seed
        self.daily = getattr(model, "daily", False)
        self.difficulty = model.difficulty
        self.current_floor = model.floor
        self.health = player.health
        self.max_health = player.max_health
        self.gold = player.gold
        self.essence = player.essence
        self.deck = list(player.cards)
        # 恢复统计
        self.stats = RunStatistics()
        for k, v in (model.run_stats or {}).items():
            if hasattr(self.stats, k):
                setattr(self.stats, k, v)
        # 恢复遗物
        self._init_relic_manager()
        for rid in player.relics:
            try:
                self.relic_manager.add_relic(rid)
            except Exception as exc:
                logger.warning("恢复遗物 %s 失败: %s", rid, exc)
        self.active = True
        self.last_battle = {}
        logger.info(
            "恢复存档: char=%s, floor=%d, hp=%d/%d, gold=%d",
            self.character_id, self.current_floor,
            self.health, self.max_health, self.gold,
        )
