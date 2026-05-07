"""
战斗系统 - 对应开发计划:
  6-5:  能量系统 (每回合3点能量, 使用卡牌消耗能量)
  6-6:  卡牌效果执行 (攻击卡/防御卡/技能卡基础效果)
  6-7:  回合制逻辑 (玩家回合和敌人回合的切换)
  6-9:  战斗结束判定 (胜利/失败判定)
  6-12: 伤害计算细化 (暴击、闪避、格挡完整伤害计算)

对应文档 §3.1 数值设计 / §10.3.2
"""
from __future__ import annotations

import logging
import random
from enum import Enum, auto
from typing import List, Optional, TYPE_CHECKING

from src.ecs.components import (
    Health, Stats, Block, Energy, BuffList,
    PlayerTag, EnemyTag, IntentDisplay, CardHolder,
)
from src.core.event_manager import event_manager
from src.utils.enums import BuffType

if TYPE_CHECKING:
    import esper
    from src.entities.cards.card import Card
    from src.entities.cards.deck import Deck

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 6-7: 战斗阶段枚举
# ═══════════════════════════════════════════════════════════════════════════════

class TurnPhase(Enum):
    """战斗回合阶段"""
    BATTLE_START = auto()       # 战斗开始
    PLAYER_TURN_START = auto()  # 玩家回合开始
    PLAYER_TURN = auto()        # 玩家行动中
    PLAYER_TURN_END = auto()    # 玩家回合结束
    ENEMY_TURN_START = auto()   # 敌人回合开始
    ENEMY_TURN = auto()         # 敌人行动中
    ENEMY_TURN_END = auto()     # 敌人回合结束
    BATTLE_WIN = auto()         # 战斗胜利
    BATTLE_LOSE = auto()        # 战斗失败


# ═══════════════════════════════════════════════════════════════════════════════
# 6-12: 伤害计算结果
# ═══════════════════════════════════════════════════════════════════════════════

class DamageResult:
    """伤害计算结果"""
    __slots__ = ("raw_damage", "final_damage", "blocked", "is_crit", "is_dodged")

    def __init__(self, raw_damage: int = 0, final_damage: int = 0,
                 blocked: int = 0, is_crit: bool = False,
                 is_dodged: bool = False) -> None:
        self.raw_damage = raw_damage
        self.final_damage = final_damage
        self.blocked = blocked
        self.is_crit = is_crit
        self.is_dodged = is_dodged


# ═══════════════════════════════════════════════════════════════════════════════
# 核心战斗管理器 (非ECS Processor，供 CombatScene 直接调用)
# ═══════════════════════════════════════════════════════════════════════════════

class CombatManager:
    """
    回合制战斗管理器。

    职责:
    - 管理战斗回合阶段 (6-7)
    - 处理卡牌使用和能量消耗 (6-5, 6-6)
    - 伤害计算 (6-12)
    - 战斗结束判定 (6-9)

    使用方式:
        manager = CombatManager(world)
        manager.start_battle()
        # 玩家点击卡牌时
        manager.play_card(card, target_entity)
        # 玩家点击结束回合
        manager.end_player_turn()
    """

    # 每回合抽卡数
    DRAW_PER_TURN = 5

    def __init__(self, world: "esper.World") -> None:
        self._world = world
        self._phase = TurnPhase.BATTLE_START
        self._turn_number = 0
        self._deck: Optional["Deck"] = None

        # 玩家实体 ID
        self._player_entity: int = -1
        # 敌人实体 ID 列表
        self._enemy_entities: List[int] = []

    # ─── 属性 ─────────────────────────────────────────────────────────────

    @property
    def phase(self) -> TurnPhase:
        return self._phase

    @property
    def turn_number(self) -> int:
        return self._turn_number

    @property
    def is_player_turn(self) -> bool:
        return self._phase == TurnPhase.PLAYER_TURN

    @property
    def is_battle_over(self) -> bool:
        return self._phase in (TurnPhase.BATTLE_WIN, TurnPhase.BATTLE_LOSE)

    # ─── 6-7: 战斗流程控制 ───────────────────────────────────────────────

    def start_battle(self, player_entity: int,
                     enemy_entities: List[int],
                     deck: "Deck") -> None:
        """
        开始战斗。
        """
        self._player_entity = player_entity
        self._enemy_entities = list(enemy_entities)
        self._deck = deck
        self._turn_number = 0
        self._phase = TurnPhase.BATTLE_START

        # 洗牌
        self._deck.shuffle_draw_pile()

        # 发布事件
        event_manager.publish("on_battle_start",
                              player=player_entity,
                              enemies=enemy_entities)

        # 进入第一个玩家回合
        self._start_player_turn()

    def _start_player_turn(self) -> None:
        """玩家回合开始"""
        self._turn_number += 1
        self._phase = TurnPhase.PLAYER_TURN_START

        # 6-5: 恢复能量
        self._restore_energy()

        # 清除玩家格挡(每回合开始清零)
        self._clear_player_block()

        # 抽卡
        if self._deck:
            self._deck.draw(self.DRAW_PER_TURN)

        # 更新敌人意图
        self._update_enemy_intents()

        # 切换到玩家行动阶段
        self._phase = TurnPhase.PLAYER_TURN

        event_manager.publish("on_player_turn_start",
                              turn=self._turn_number)
        logger.info("玩家回合 %d 开始", self._turn_number)

    def end_player_turn(self) -> None:
        """
        玩家点击"结束回合"时调用。
        """
        if self._phase != TurnPhase.PLAYER_TURN:
            return

        self._phase = TurnPhase.PLAYER_TURN_END

        # 弃掉所有手牌
        if self._deck:
            self._deck.discard_hand()

        event_manager.publish("on_player_turn_end", turn=self._turn_number)

        # 进入敌人回合
        self._start_enemy_turn()

    def _start_enemy_turn(self) -> None:
        """敌人回合开始"""
        self._phase = TurnPhase.ENEMY_TURN_START

        # 清除敌人格挡
        self._clear_enemy_blocks()

        self._phase = TurnPhase.ENEMY_TURN

        event_manager.publish("on_enemy_turn_start", turn=self._turn_number)
        logger.info("敌人回合开始")

    def execute_enemy_actions(self) -> List[dict]:
        """
        执行所有存活敌人的行动 (6-8 调用)。
        返回行动结果列表。
        """
        results = []
        for eid in self._enemy_entities:
            if not self._is_entity_alive(eid):
                continue
            result = self._execute_single_enemy_action(eid)
            if result:
                results.append(result)

            # 检查玩家是否死亡
            if not self._is_entity_alive(self._player_entity):
                self._phase = TurnPhase.BATTLE_LOSE
                event_manager.publish("on_battle_lose")
                return results

        # 敌人回合结束，检查战斗状态
        self._end_enemy_turn()
        return results

    def _end_enemy_turn(self) -> None:
        """敌人回合结束"""
        if self.is_battle_over:
            return

        self._phase = TurnPhase.ENEMY_TURN_END

        # 7-2: 回合结束时处理所有 buff tick 效果
        self._process_buff_ticks()

        event_manager.publish("on_enemy_turn_end", turn=self._turn_number)

        # 检查是否有实体因 buff tick 死亡
        self._check_battle_end()
        if self.is_battle_over:
            return

        # 检查胜利条件
        if self._check_all_enemies_dead():
            self._phase = TurnPhase.BATTLE_WIN
            event_manager.publish("on_battle_win")
            logger.info("战斗胜利!")
        else:
            # 开始新的玩家回合
            self._start_player_turn()

    # ─── 6-5 / 6-6: 卡牌使用 ─────────────────────────────────────────────

    def play_card(self, card: "Card",
                  target_entity: Optional[int] = None) -> bool:
        """
        使用卡牌。

        :param card: 要使用的卡牌
        :param target_entity: 目标实体 ID (攻击卡需要)
        :return: True 表示成功使用
        """
        if self._phase != TurnPhase.PLAYER_TURN:
            return False

        # 6-5: 检查能量
        if not self._can_afford(card.cost):
            logger.info("能量不足: 需要 %d", card.cost)
            return False

        # 6-5: 消耗能量
        self._spend_energy(card.cost)

        # 6-6: 执行卡牌效果
        self._execute_card_effect(card, target_entity)

        # 卡牌从手牌移到弃牌堆/消耗堆
        if self._deck:
            self._deck.play_card(card)

        event_manager.publish("on_card_played",
                              card=card, target=target_entity)
        logger.info("使用卡牌: %s", card.display_name)

        # 6-9: 检查战斗是否结束
        self._check_battle_end()

        return True

    def _execute_card_effect(self, card: "Card",
                             target_entity: Optional[int]) -> None:
        """
        执行卡牌效果 (6-6)。
        """
        effect = card.active_effect

        # 攻击卡: 对目标造成伤害
        if effect.damage > 0:
            if effect.aoe:
                # 范围伤害: 对所有存活敌人
                for eid in self._enemy_entities:
                    if self._is_entity_alive(eid):
                        self._deal_damage_to(
                            self._player_entity, eid, effect.damage
                        )
            elif target_entity is not None:
                self._deal_damage_to(
                    self._player_entity, target_entity, effect.damage
                )
            else:
                # 无目标时攻击第一个存活敌人
                first_alive = self._get_first_alive_enemy()
                if first_alive is not None:
                    self._deal_damage_to(
                        self._player_entity, first_alive, effect.damage
                    )

        # 防御卡: 获得格挡
        if effect.block > 0:
            self._add_block(self._player_entity, effect.block)

        # 抽卡
        if effect.draw > 0 and self._deck:
            self._deck.draw(effect.draw)

        # 治疗
        if effect.heal > 0:
            self._heal_entity(self._player_entity, effect.heal)

        # 获得能量
        if effect.energy_gain > 0:
            self._gain_energy(effect.energy_gain)

        # 施加 buff
        if effect.apply_buff:
            buff_target = target_entity if effect.buff_target == "enemy" else self._player_entity
            if buff_target is None:
                buff_target = self._get_first_alive_enemy()
            if buff_target is not None:
                self._apply_buff(buff_target, effect.apply_buff, effect.buff_stacks)

        # 永久增加最大生命
        if effect.max_health_bonus > 0:
            self._increase_max_health(self._player_entity, effect.max_health_bonus)

        # 永久增加攻击力
        if effect.attack_bonus > 0:
            self._increase_attack(self._player_entity, effect.attack_bonus)

    # ─── 6-12: 伤害计算 ──────────────────────────────────────────────────

    def _deal_damage_to(self, attacker: int, target: int,
                        base_damage: int) -> DamageResult:
        """
        完整伤害计算流程:
        1. 获取攻击者属性加成（力量buff等）
        2. 检查闪避
        3. 检查暴击
        4. 应用格挡
        5. 扣除HP
        """
        result = DamageResult()
        result.raw_damage = base_damage

        try:
            attacker_stats = self._world.component_for_entity(attacker, Stats)
            target_stats = self._world.component_for_entity(target, Stats)
            target_hp = self._world.component_for_entity(target, Health)
            target_block = self._world.component_for_entity(target, Block)
        except (KeyError, Exception):
            return result

        # Buff 加成 (7-4)
        attacker_buffs = self._get_buffs(attacker)
        target_buffs = self._get_buffs(target)

        # 力量：攻击伤害 +N（N为层数）
        strength = attacker_buffs.get_stacks(BuffType.STRENGTH.value) if attacker_buffs else 0
        damage = base_damage + strength

        # 虚弱：攻击伤害 ×0.75
        if attacker_buffs and attacker_buffs.has_buff(BuffType.WEAKENED.value):
            damage = int(damage * 0.75)

        # 闪避检查
        dodge_rate = target_stats.dodge_rate
        if random.random() < dodge_rate:
            result.is_dodged = True
            result.final_damage = 0
            event_manager.publish("on_dodge", target=target)
            logger.info("闪避! 目标实体 %d", target)
            return result

        # 暴击检查
        crit_rate = attacker_stats.crit_rate
        if random.random() < crit_rate:
            damage = int(damage * attacker_stats.crit_multiplier)
            result.is_crit = True

        # 易伤：受到伤害 ×1.5
        if target_buffs and target_buffs.has_buff(BuffType.VULNERABLE.value):
            damage = int(damage * 1.5)

        # 格挡优先抵消伤害
        if target_block.current > 0:
            remaining = target_block.absorb_damage(damage)
            result.blocked = damage - remaining
            damage = remaining

        # 最终伤害
        result.final_damage = max(0, damage)

        # 扣血
        if result.final_damage > 0:
            target_hp.take_damage(result.final_damage)

        # 发布事件
        event_manager.publish("on_damage_dealt",
                              attacker=attacker, target=target,
                              result=result)

        return result

    # ─── 6-8: 敌人行动执行 ───────────────────────────────────────────────

    def _execute_single_enemy_action(self, eid: int) -> Optional[dict]:
        """执行单个敌人的行动"""
        try:
            intent = self._world.component_for_entity(eid, IntentDisplay)
            enemy_stats = self._world.component_for_entity(eid, Stats)
        except (KeyError, Exception):
            return None

        action_result = {
            "entity": eid,
            "type": intent.intent_type,
            "value": intent.intent_value,
        }

        if intent.intent_type == "attack":
            # 敌人攻击玩家
            result = self._deal_damage_to(eid, self._player_entity, intent.intent_value)
            action_result["damage_result"] = result

        elif intent.intent_type == "defend":
            # 敌人获得格挡
            self._add_block(eid, intent.intent_value)

        elif intent.intent_type == "buff":
            # 敌人给自己加 力量 buff
            self._apply_buff(eid, BuffType.STRENGTH.value, 2)

        elif intent.intent_type == "debuff":
            # 敌人给玩家加 虚弱 debuff
            self._apply_buff(self._player_entity, BuffType.WEAKENED.value, 1)

        return action_result

    def _update_enemy_intents(self) -> None:
        """
        更新所有敌人的行动意图（在玩家回合开始时显示）。
        敌人根据 AI 模式随机选择下回合行动。
        """
        for eid in self._enemy_entities:
            if not self._is_entity_alive(eid):
                continue
            try:
                intent = self._world.component_for_entity(eid, IntentDisplay)
                stats = self._world.component_for_entity(eid, Stats)
            except (KeyError, Exception):
                continue

            # 简单的AI: 随机选择攻击或防御
            roll = random.random()
            if roll < 0.6:
                # 攻击
                intent.intent_type = "attack"
                intent.intent_value = stats.attack
                intent.description = f"攻击 {stats.attack}"
            elif roll < 0.85:
                # 防御
                intent.intent_type = "defend"
                intent.intent_value = 5 + stats.defense
                intent.description = f"格挡 {5 + stats.defense}"
            else:
                # Buff/Debuff
                if random.random() < 0.5:
                    intent.intent_type = "buff"
                    intent.intent_value = 2
                    intent.description = "强化自身"
                else:
                    intent.intent_type = "debuff"
                    intent.intent_value = 1
                    intent.description = "削弱玩家"

    # ─── 6-9: 战斗结束判定 ───────────────────────────────────────────────

    def _check_battle_end(self) -> None:
        """检查战斗是否结束"""
        # 玩家死亡 → 失败
        if not self._is_entity_alive(self._player_entity):
            self._phase = TurnPhase.BATTLE_LOSE
            event_manager.publish("on_battle_lose")
            logger.info("战斗失败: 玩家死亡")
            return

        # 所有敌人死亡 → 胜利
        if self._check_all_enemies_dead():
            self._phase = TurnPhase.BATTLE_WIN
            event_manager.publish("on_battle_win")
            logger.info("战斗胜利: 所有敌人被消灭")

    def _check_all_enemies_dead(self) -> bool:
        """检查是否所有敌人都已死亡"""
        for eid in self._enemy_entities:
            if self._is_entity_alive(eid):
                return False
        return True

    # ─── 辅助方法 ─────────────────────────────────────────────────────────

    def _is_entity_alive(self, entity: int) -> bool:
        """检查实体是否存活"""
        try:
            hp = self._world.component_for_entity(entity, Health)
            return hp.is_alive
        except (KeyError, Exception):
            return False

    def _can_afford(self, cost: int) -> bool:
        """检查玩家能量是否足够"""
        try:
            energy = self._world.component_for_entity(self._player_entity, Energy)
            return energy.current >= cost
        except (KeyError, Exception):
            return False

    def _spend_energy(self, cost: int) -> None:
        """消耗能量"""
        try:
            energy = self._world.component_for_entity(self._player_entity, Energy)
            energy.spend(cost)
        except (KeyError, Exception):
            pass

    def _gain_energy(self, amount: int) -> None:
        """获得能量"""
        try:
            energy = self._world.component_for_entity(self._player_entity, Energy)
            energy.current = min(energy.current + amount, energy.maximum + 3)
        except (KeyError, Exception):
            pass

    def _restore_energy(self) -> None:
        """6-5: 回合开始恢复满能量"""
        try:
            energy = self._world.component_for_entity(self._player_entity, Energy)
            energy.restore_full()
        except (KeyError, Exception):
            pass

    def _clear_player_block(self) -> None:
        """清除玩家格挡（每回合清空）"""
        try:
            block = self._world.component_for_entity(self._player_entity, Block)
            block.reset()
        except (KeyError, Exception):
            pass

    def _process_buff_ticks(self) -> None:
        """7-2: 回合结束时处理所有实体的 buff tick 效果"""
        from src.systems.buff_system import BuffProcessor
        processor = BuffProcessor(self._world)
        processor.process_turn_end()

    def _clear_enemy_blocks(self) -> None:
        """清除所有敌人格挡"""
        for eid in self._enemy_entities:
            try:
                block = self._world.component_for_entity(eid, Block)
                block.reset()
            except (KeyError, Exception):
                pass

    def _add_block(self, entity: int, amount: int) -> None:
        """给实体添加格挡"""
        try:
            block = self._world.component_for_entity(entity, Block)
            block.add_block(amount)
            event_manager.publish("on_block_gained", entity=entity, amount=amount)
        except (KeyError, Exception):
            pass

    def _heal_entity(self, entity: int, amount: int) -> None:
        """治疗实体"""
        try:
            hp = self._world.component_for_entity(entity, Health)
            actual = hp.heal(amount)
            if actual > 0:
                event_manager.publish("on_heal", entity=entity, amount=actual)
        except (KeyError, Exception):
            pass

    def _apply_buff(self, entity: int, buff_type: str, stacks: int) -> None:
        """施加 buff (委托给 buff_system.apply_buff 统一接口)"""
        from src.systems.buff_system import apply_buff
        apply_buff(self._world, entity, buff_type, value=stacks)

    def _get_buffs(self, entity: int) -> Optional[BuffList]:
        """获取实体的 BuffList"""
        try:
            return self._world.component_for_entity(entity, BuffList)
        except (KeyError, Exception):
            return None

    def _get_first_alive_enemy(self) -> Optional[int]:
        """获取第一个存活的敌人"""
        for eid in self._enemy_entities:
            if self._is_entity_alive(eid):
                return eid
        return None

    def _increase_max_health(self, entity: int, amount: int) -> None:
        """永久增加最大生命值"""
        try:
            hp = self._world.component_for_entity(entity, Health)
            hp.maximum += amount
            hp.current += amount
        except (KeyError, Exception):
            pass

    def _increase_attack(self, entity: int, amount: int) -> None:
        """永久增加攻击力"""
        try:
            stats = self._world.component_for_entity(entity, Stats)
            stats.attack += amount
        except (KeyError, Exception):
            pass

    def get_player_energy(self) -> tuple:
        """获取玩家当前/最大能量"""
        try:
            energy = self._world.component_for_entity(self._player_entity, Energy)
            return energy.current, energy.maximum
        except (KeyError, Exception):
            return 0, 0


# ═══════════════════════════════════════════════════════════════════════════════
# ECS Processor (可选，用于 esper 世界中的每帧处理)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import esper

    class CombatProcessor(esper.Processor):
        """ECS战斗处理器 - 处理持续性战斗效果（如DOT）"""
        def process(self, dt: float) -> None:
            # 处理 DOT 效果等持续性伤害
            # 主要战斗逻辑由 CombatManager 驱动
            pass

except ImportError:
    class CombatProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
