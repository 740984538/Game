"""
Buff/Debuff 系统 - 对应开发计划:
  7-2: Buff 处理器 (每回合结束衰减层数/持续时间并触发 tick 效果)
  7-3: Buff 施加接口 (统一的 apply_buff 工具函数)

对应文档 §5.3 / §3.1.1 特殊机制

完成标志 (7-2):
  - 回合结束时遍历所有实体的 BuffList
  - 持续时间类 buff（如虚弱）每回合 duration -1，归零时移除
  - 层数类 buff（如中毒）每回合造成等于层数的伤害，然后 stacks -1
  - 燃烧每回合造成固定伤害
  - 已失效 buff 自动从列表移除

完成标志 (7-3):
  - apply_buff(entity_id, buff_type, value) 接口统一
  - 相同 buff 叠加时合并层数（叠层型）或刷新持续时间（刷新型）
  - 施加 buff 后发布 on_buff_applied 事件
"""
from __future__ import annotations

import logging
from typing import List, Optional, TYPE_CHECKING

from src.ecs.components import BuffList, BuffInstance, Health
from src.core.event_manager import event_manager
from src.utils.enums import BuffType

if TYPE_CHECKING:
    import esper

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Buff 元数据定义: 每种 Buff 的行为特征
# ═══════════════════════════════════════════════════════════════════════════════

# 叠层型 buff: 相同 buff 叠加时合并层数
# 刷新型 buff: 相同 buff 叠加时刷新持续时间
BUFF_STACK_MODE = {
    # 叠层型 (stacks 累加)
    BuffType.STRENGTH.value: "stack",
    BuffType.POISONED.value: "stack",
    BuffType.BURNING.value: "stack",
    BuffType.VULNERABLE.value: "stack",
    BuffType.WEAKENED.value: "stack",
    BuffType.REGENERATION.value: "stack",
    # 刷新型 (duration 刷新)
    BuffType.STEALTH.value: "refresh",
    BuffType.FROZEN.value: "refresh",
    BuffType.STUNNED.value: "refresh",
    # 叠层型 (格挡本身由 Block 组件处理，此处作为标记)
    BuffType.BLOCKING.value: "stack",
}

# 每种 Buff 的显示信息
BUFF_INFO = {
    BuffType.STRENGTH.value: {
        "name": "力量",
        "description": "攻击伤害 +{stacks}",
        "color": (220, 100, 40),
        "is_debuff": False,
    },
    BuffType.WEAKENED.value: {
        "name": "虚弱",
        "description": "攻击伤害 ×0.75",
        "color": (120, 180, 60),
        "is_debuff": True,
    },
    BuffType.VULNERABLE.value: {
        "name": "易伤",
        "description": "受到伤害 ×1.5",
        "color": (200, 60, 200),
        "is_debuff": True,
    },
    BuffType.POISONED.value: {
        "name": "中毒",
        "description": "每回合受到{stacks}点伤害，然后层数-1",
        "color": (80, 200, 60),
        "is_debuff": True,
    },
    BuffType.BURNING.value: {
        "name": "燃烧",
        "description": "每回合受到{stacks}点火焰伤害",
        "color": (240, 120, 20),
        "is_debuff": True,
    },
    BuffType.REGENERATION.value: {
        "name": "再生",
        "description": "每回合恢复{stacks}点HP",
        "color": (60, 220, 100),
        "is_debuff": False,
    },
    BuffType.STEALTH.value: {
        "name": "隐身",
        "description": "不会被敌人攻击，持续{duration}回合",
        "color": (160, 160, 200),
        "is_debuff": False,
    },
    BuffType.FROZEN.value: {
        "name": "冰冻",
        "description": "无法行动，持续{duration}回合",
        "color": (100, 200, 240),
        "is_debuff": True,
    },
    BuffType.STUNNED.value: {
        "name": "眩晕",
        "description": "无法行动，持续{duration}回合",
        "color": (240, 240, 60),
        "is_debuff": True,
    },
    BuffType.BLOCKING.value: {
        "name": "格挡",
        "description": "抵消{stacks}点伤害",
        "color": (80, 140, 200),
        "is_debuff": False,
    },
}


def get_buff_info(buff_type: str) -> dict:
    """获取 buff 的显示信息"""
    return BUFF_INFO.get(buff_type, {
        "name": buff_type,
        "description": "",
        "color": (120, 120, 120),
        "is_debuff": False,
    })


def get_buff_tooltip(buff_type: str, stacks: int, duration: int) -> str:
    """获取 buff 的 tooltip 文本（名称+说明）"""
    info = get_buff_info(buff_type)
    name = info["name"]
    desc = info["description"].format(stacks=stacks, duration=duration)
    return f"{name}: {desc}"


# ═══════════════════════════════════════════════════════════════════════════════
# 7-3: 统一 Buff 施加接口
# ═══════════════════════════════════════════════════════════════════════════════

def apply_buff(world: "esper.World", entity_id: int,
               buff_type: str, value: int = 1,
               duration: int = -1, source: int = -1) -> None:
    """
    统一的 Buff 施加接口 (7-3)。
    卡牌效果、遗物效果均通过此函数施加 buff。

    :param world:     ECS 世界
    :param entity_id: 目标实体 ID
    :param buff_type: buff 类型字符串 (对应 BuffType 枚举值)
    :param value:     层数(叠层型) 或 持续回合数(刷新型)
    :param duration:  持续回合数 (-1 为永久，仅叠层型需要额外指定)
    :param source:    施加来源实体 ID

    叠加规则:
      - 叠层型: 相同 buff 合并层数 (stacks += value)
      - 刷新型: 相同 buff 刷新持续时间 (duration = max(current, value))

    施加后发布 on_buff_applied 事件。
    """
    try:
        buff_list = world.component_for_entity(entity_id, BuffList)
    except (KeyError, Exception):
        return

    mode = BUFF_STACK_MODE.get(buff_type, "stack")

    if mode == "refresh":
        # 刷新型: value 作为 duration
        _apply_refresh_buff(buff_list, buff_type, value, source)
    else:
        # 叠层型: value 作为 stacks
        _apply_stack_buff(buff_list, buff_type, value, duration, source)

    # 发布事件
    event_manager.publish("on_buff_applied",
                          entity=entity_id,
                          buff_type=buff_type,
                          stacks=value)

    logger.debug("施加 buff: entity=%d, type=%s, value=%d",
                 entity_id, buff_type, value)


def remove_buff(world: "esper.World", entity_id: int, buff_type: str) -> None:
    """移除指定实体的指定 buff"""
    try:
        buff_list = world.component_for_entity(entity_id, BuffList)
    except (KeyError, Exception):
        return

    buff_list.remove_buff(buff_type)

    event_manager.publish("on_buff_removed",
                          entity=entity_id,
                          buff_type=buff_type)


def _apply_stack_buff(buff_list: BuffList, buff_type: str,
                      stacks: int, duration: int, source: int) -> None:
    """叠层型 buff: 合并层数"""
    for buff in buff_list.buffs:
        if buff.buff_type == buff_type:
            buff.stacks += stacks
            # 如果传入了正的 duration 且原来是永久的，不覆盖
            if duration > 0 and buff.duration > 0:
                buff.duration = max(buff.duration, duration)
            elif duration > 0 and buff.duration == -1:
                pass  # 保持永久
            return

    # 新增 buff
    buff_list.buffs.append(BuffInstance(
        buff_type=buff_type,
        stacks=stacks,
        duration=duration,
        source_entity=source,
    ))


def _apply_refresh_buff(buff_list: BuffList, buff_type: str,
                        duration: int, source: int) -> None:
    """刷新型 buff: 刷新持续时间"""
    for buff in buff_list.buffs:
        if buff.buff_type == buff_type:
            buff.duration = max(buff.duration, duration)
            return

    # 新增 buff
    buff_list.buffs.append(BuffInstance(
        buff_type=buff_type,
        stacks=1,
        duration=duration,
        source_entity=source,
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# 7-2: Buff 处理器
# ═══════════════════════════════════════════════════════════════════════════════

class BuffProcessor:
    """
    Buff 处理器 (7-2)。
    在每回合结束时调用，处理所有实体的 buff 衰减和 tick 效果。

    使用方式:
        processor = BuffProcessor(world)
        processor.process_turn_end()  # 每回合结束调用一次
    """

    # 燃烧每层每回合造成的伤害
    BURN_DAMAGE_PER_STACK = 3

    def __init__(self, world: "esper.World") -> None:
        self._world = world

    def process_turn_end(self) -> List[dict]:
        """
        回合结束时处理所有 buff。
        返回本回合 buff 触发的效果列表（用于 UI 显示）。

        处理逻辑:
          - 持续时间类 buff: duration -1，归零时移除
          - 中毒: 造成等于层数的伤害，然后 stacks -1，归零时移除
          - 燃烧: 每回合造成固定伤害 (3 × 层数)
          - 再生: 每回合恢复等于层数的 HP
          - 已失效 buff 自动移除
        """
        effects: List[dict] = []

        try:
            import esper
            entities = self._world.get_components(BuffList, Health)
        except (ImportError, Exception):
            return effects

        for ent, (buff_list, health) in entities:
            expired: List[BuffInstance] = []

            for buff in buff_list.buffs:
                effect = self._tick_buff(ent, buff, health)
                if effect:
                    effects.append(effect)

                # 检查是否过期
                if self._is_expired(buff):
                    expired.append(buff)

            # 移除过期 buff
            for buff in expired:
                buff_list.buffs.remove(buff)
                event_manager.publish("on_buff_expired",
                                      entity=ent,
                                      buff_type=buff.buff_type)
                logger.debug("Buff 过期: entity=%d, type=%s", ent, buff.buff_type)

        return effects

    def _tick_buff(self, entity: int, buff: BuffInstance,
                   health: Health) -> Optional[dict]:
        """
        处理单个 buff 的回合 tick 效果。
        返回效果描述字典（如有）。
        """
        buff_type = buff.buff_type

        # 中毒: 造成等于层数的伤害，然后 stacks -1
        if buff_type == BuffType.POISONED.value:
            damage = buff.stacks
            health.take_damage(damage)
            buff.stacks -= 1
            event_manager.publish("on_poison_tick",
                                  entity=entity, damage=damage)
            return {
                "entity": entity,
                "type": "poison",
                "damage": damage,
                "remaining_stacks": buff.stacks,
            }

        # 燃烧: 每回合造成固定伤害 (3 × 层数)
        if buff_type == BuffType.BURNING.value:
            damage = self.BURN_DAMAGE_PER_STACK * buff.stacks
            health.take_damage(damage)
            event_manager.publish("on_burn_tick",
                                  entity=entity, damage=damage)
            return {
                "entity": entity,
                "type": "burn",
                "damage": damage,
                "stacks": buff.stacks,
            }

        # 再生: 每回合恢复等于层数的 HP
        if buff_type == BuffType.REGENERATION.value:
            heal_amount = buff.stacks
            actual = health.heal(heal_amount)
            if actual > 0:
                event_manager.publish("on_regen_tick",
                                      entity=entity, heal=actual)
                return {
                    "entity": entity,
                    "type": "regen",
                    "heal": actual,
                    "stacks": buff.stacks,
                }

        # 持续时间类 buff: duration -1
        if buff.duration > 0:
            buff.duration -= 1

        return None

    def _is_expired(self, buff: BuffInstance) -> bool:
        """判断 buff 是否已失效"""
        # 层数归零
        if buff.stacks <= 0:
            return True
        # 持续时间归零 (永久 buff duration=-1 不会过期)
        if buff.duration == 0:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# ECS Processor 兼容包装
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import esper

    class BuffECSProcessor(esper.Processor):
        """
        ECS 兼容的 Buff 处理器。
        注意：回合制游戏中不在每帧处理 buff，
        而是由 CombatManager 在回合结束时调用 BuffProcessor.process_turn_end()。
        此处保留接口用于可能的实时效果。
        """
        def process(self, dt: float) -> None:
            # 回合制下不做每帧处理
            # buff 的 tick 由 BuffProcessor.process_turn_end() 驱动
            pass

except ImportError:
    class BuffECSProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
