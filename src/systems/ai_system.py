"""
AI 系统 - 对应开发计划 6-8
实现敌人回合自动选择行动（攻击/防御/技能）。

完成标志:
  - 敌人根据配置的行动模式选择行为
  - 攻击：对玩家造成伤害
  - 防御：获得格挡
  - 技能：执行特殊效果
  - 行动意图在玩家回合显示

对应文档 §4.2 战斗房间设计
"""
from __future__ import annotations

import random
import logging
from typing import List, Optional, TYPE_CHECKING

from src.ecs.components import (
    AIController, IntentDisplay, Position, Velocity,
    EnemyTag, PlayerTag, Health, Stats, Block, BuffList,
    BossController, SkillSet,
)
from src.core.event_manager import event_manager

if TYPE_CHECKING:
    import esper

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# AI 行为模式定义
# ═══════════════════════════════════════════════════════════════════════════════

# 各AI模式的攻击/防御/buff概率
AI_PATTERNS = {
    "melee_aggressive": {
        "attack_weight": 0.70,
        "defend_weight": 0.20,
        "buff_weight": 0.05,
        "debuff_weight": 0.05,
    },
    "melee_slow": {
        "attack_weight": 0.50,
        "defend_weight": 0.35,
        "buff_weight": 0.10,
        "debuff_weight": 0.05,
    },
    "ranged_kite": {
        "attack_weight": 0.60,
        "defend_weight": 0.15,
        "buff_weight": 0.05,
        "debuff_weight": 0.20,
    },
    "elite_melee": {
        "attack_weight": 0.55,
        "defend_weight": 0.20,
        "buff_weight": 0.15,
        "debuff_weight": 0.10,
    },
    "elite_ranged": {
        "attack_weight": 0.50,
        "defend_weight": 0.10,
        "buff_weight": 0.15,
        "debuff_weight": 0.25,
    },
    "defensive": {
        "attack_weight": 0.30,
        "defend_weight": 0.50,
        "buff_weight": 0.15,
        "debuff_weight": 0.05,
    },
}


class EnemyAI:
    """
    敌人 AI 管理器。
    为每个敌人实体决定下回合的行动意图。

    使用方式:
        ai = EnemyAI(world)
        ai.decide_intents(enemy_entities)
    """

    def __init__(self, world: "esper.World") -> None:
        self._world = world

    def decide_intents(self, enemy_entities: List[int]) -> None:
        """
        为所有存活敌人决定下回合行动意图。
        在玩家回合开始时调用。
        """
        for eid in enemy_entities:
            if not self._is_alive(eid):
                continue
            self._decide_single_intent(eid)

    def _decide_single_intent(self, eid: int) -> None:
        """为单个敌人决定意图"""
        try:
            ai = self._world.component_for_entity(eid, AIController)
            intent = self._world.component_for_entity(eid, IntentDisplay)
            stats = self._world.component_for_entity(eid, Stats)
            hp = self._world.component_for_entity(eid, Health)
        except (KeyError, Exception):
            return

        # 获取AI模式
        pattern = AI_PATTERNS.get(ai.ai_pattern, AI_PATTERNS["melee_aggressive"])

        # 低HP时增加防御倾向
        hp_ratio = hp.ratio
        attack_w = pattern["attack_weight"]
        defend_w = pattern["defend_weight"]
        buff_w = pattern["buff_weight"]
        debuff_w = pattern["debuff_weight"]

        if hp_ratio < 0.3:
            # 低血量偏防御
            defend_w *= 2.0
            attack_w *= 0.6

        # 检查是否有 BOSS 阶段控制器
        try:
            boss_ctrl = self._world.component_for_entity(eid, BossController)
            self._decide_boss_intent(eid, intent, stats, boss_ctrl, hp_ratio)
            return
        except (KeyError, Exception):
            pass

        # 加权随机选择
        actions = ["attack", "defend", "buff", "debuff"]
        weights = [attack_w, defend_w, buff_w, debuff_w]
        total = sum(weights)
        weights = [w / total for w in weights]

        roll = random.random()
        cumulative = 0.0
        chosen = "attack"
        for action, weight in zip(actions, weights):
            cumulative += weight
            if roll <= cumulative:
                chosen = action
                break

        # 设置意图
        if chosen == "attack":
            # 攻击力 = 基础攻击 + buff加成
            damage = stats.attack
            try:
                buffs = self._world.component_for_entity(eid, BuffList)
                damage += buffs.get_stacks("berserking")
            except (KeyError, Exception):
                pass
            intent.intent_type = "attack"
            intent.intent_value = damage
            intent.description = f"攻击 {damage}"

        elif chosen == "defend":
            block_val = 5 + stats.defense
            intent.intent_type = "defend"
            intent.intent_value = block_val
            intent.description = f"格挡 {block_val}"

        elif chosen == "buff":
            intent.intent_type = "buff"
            intent.intent_value = 2
            intent.description = "强化: 攻击+2"

        elif chosen == "debuff":
            intent.intent_type = "debuff"
            intent.intent_value = 1
            intent.description = "削弱: 虚弱1层"

    def _decide_boss_intent(self, eid: int, intent: IntentDisplay,
                            stats: Stats, boss: BossController,
                            hp_ratio: float) -> None:
        """BOSS 特殊意图决策（含阶段切换事件）"""
        # 检查阶段切换
        old_phase = boss.current_phase
        if boss.check_phase_transition(hp_ratio):
            new_phase_data = boss.get_current_phase_data()
            event_manager.publish(
                "on_boss_phase_change",
                entity=eid,
                boss_name=boss.boss_name,
                old_phase=old_phase,
                new_phase=boss.current_phase,
                description=new_phase_data.description if new_phase_data else "",
            )
            logger.info(
                "BOSS %s 进入阶段 %d: %s",
                boss.boss_name, boss.current_phase,
                new_phase_data.description if new_phase_data else "",
            )

        phase_data = boss.get_current_phase_data()

        # BOSS 行为按阶段差异化
        if boss.current_phase >= 3:
            # 狂暴阶段: 高伤害攻击
            intent.intent_type = "attack"
            intent.intent_value = int(stats.attack * 1.5)
            intent.description = f"狂暴攻击 {intent.intent_value}"
        elif boss.current_phase == 2:
            # 第二阶段: 交替攻击和技能
            if random.random() < 0.6:
                intent.intent_type = "attack"
                intent.intent_value = stats.attack
                intent.description = f"攻击 {stats.attack}"
            else:
                intent.intent_type = "buff"
                intent.intent_value = 3
                intent.description = "强化: 攻击+3"
        else:
            # 第一阶段: 正常攻击模式
            if random.random() < 0.7:
                intent.intent_type = "attack"
                intent.intent_value = stats.attack
                intent.description = f"攻击 {stats.attack}"
            else:
                intent.intent_type = "defend"
                intent.intent_value = 10 + stats.defense
                intent.description = f"格挡 {10 + stats.defense}"

    def _is_alive(self, entity: int) -> bool:
        """检查实体是否存活"""
        try:
            hp = self._world.component_for_entity(entity, Health)
            return hp.is_alive
        except (KeyError, Exception):
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# ECS Processor (esper 兼容)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import esper

    class AIProcessor(esper.Processor):
        """
        AI 处理器 - 实时 AI 行为（非回合制部分）。
        注意：回合制 AI 意图决策由 EnemyAI 类处理，
        此 Processor 用于处理非回合制的实时行为（如动画状态等）。
        """
        def process(self, dt: float) -> None:
            # 回合制战斗中不需要实时AI
            # 保留此 Processor 用于未来可能的实时元素
            pass

except ImportError:
    class AIProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
