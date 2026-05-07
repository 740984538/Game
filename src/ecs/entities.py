"""
实体工厂
负责创建带有预设组件的游戏实体。
对应开发计划: 5-2 实体工厂

提供:
  - EntityFactory 类: 统一的实体创建入口
  - create_player: 根据角色配置创建玩家实体 (向后兼容的模块级函数)
  - create_enemy:  根据敌人配置创建敌人实体 (向后兼容的模块级函数)
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from src.ecs.components import (
    Position, Velocity, Collider,
    Sprite, Health, Stats, Block, Energy,
    Combat, Renderable, Animation,
    BuffList, Wallet,
    PlayerTag, EnemyTag,
    AIController, IntentDisplay,
    BossController, BossPhaseData,
    CardHolder, RelicHolder, SkillSet, SkillSlot, DropTable,
)

if TYPE_CHECKING:
    import esper


# ═══════════════════════════════════════════════════════════════════════════════
# EntityFactory 类
# ═══════════════════════════════════════════════════════════════════════════════

class EntityFactory:
    """
    实体工厂，根据配置创建完整的 ECS 实体。

    使用方式:
        factory = EntityFactory(world)
        player_id = factory.create_player(char_config, x=200, y=400)
        enemy_id  = factory.create_enemy(enemy_config, x=800, y=300)

    对应文档 §10.3.1 ECS架构
    """

    def __init__(self, world: "esper.World") -> None:
        self._world = world

    # ── 玩家创建 ──────────────────────────────────────────────────────────

    def create_player(self, char_config: dict,
                      x: float = 200.0, y: float = 400.0) -> int:
        """
        根据角色配置创建玩家实体。

        :param char_config: config/characters/*.yaml 中的 character 节
                            必须包含 'id', 'base_stats' 字段
        :param x, y: 战斗场景中的初始坐标
        :return: 实体 ID
        """
        char_id = char_config["id"]
        stats = char_config["base_stats"]

        # 基础属性
        health_val = stats.get("health", 80)
        attack_val = stats.get("attack", 10)
        defense_val = stats.get("defense", 5)
        speed_val = float(stats.get("speed", 5))
        crit_rate = float(stats.get("crit_rate", 0.05))
        dodge_rate = float(stats.get("dodge_rate", 0.0))

        # 起始卡组
        starting_deck = char_config.get("starting_deck", [])

        # 起始遗物
        starting_relic = char_config.get("starting_relic", "")
        relic_ids = [starting_relic] if starting_relic else []

        entity = self._world.create_entity(
            # 标签
            PlayerTag(character_id=char_id),
            # 物理
            Position(x=x, y=y),
            Velocity(),
            Collider(width=64, height=80),
            # 渲染
            Sprite(
                sprite_key=f"char_{char_id}_idle",
                width=64, height=80,
                color=(60, 120, 180),  # 蓝色占位
            ),
            Animation(current_anim="idle"),
            # 战斗属性
            Health(current=health_val, maximum=health_val),
            Stats(
                attack=attack_val,
                defense=defense_val,
                speed=speed_val,
                crit_rate=crit_rate,
                crit_multiplier=1.5,
                dodge_rate=dodge_rate,
            ),
            Block(),
            Energy(current=3, maximum=3),
            # 系统
            BuffList(),
            Wallet(gold=char_config.get("starting_gold", 100)),
            CardHolder(deck=list(starting_deck)),
            RelicHolder(relic_ids=relic_ids),
            # 向后兼容: 部分系统可能依赖旧组件
            Combat(
                attack=attack_val,
                defense=defense_val,
                speed=speed_val,
                crit_rate=crit_rate,
                dodge_rate=dodge_rate,
            ),
            Renderable(sprite_key=f"char_{char_id}_idle", layer=1),
        )
        return entity

    # ── 敌人创建 ──────────────────────────────────────────────────────────

    def create_enemy(self, enemy_config: dict,
                     x: float = 800.0, y: float = 300.0) -> int:
        """
        根据敌人配置创建敌人实体。

        :param enemy_config: config/enemies/*.yaml 中的单条 enemy 节
                             必须包含 'id', 'base_stats' 字段
        :param x, y: 战斗场景中的初始坐标
        :return: 实体 ID
        """
        enemy_id = enemy_config["id"]
        enemy_type = enemy_config.get("type", "common")
        enemy_name = enemy_config.get("name", enemy_id)
        stats = enemy_config["base_stats"]

        # 基础属性
        health_val = stats.get("health", 30)
        attack_val = stats.get("attack", 8)
        defense_val = stats.get("defense", 2)
        speed_val = float(stats.get("speed", 4))
        crit_rate = float(stats.get("crit_rate", 0.0))
        dodge_rate = float(stats.get("dodge_rate", 0.0))

        # 根据敌人类型确定精灵大小和颜色
        sprite_w, sprite_h, sprite_color = self._enemy_sprite_params(enemy_type)

        # 基础组件
        components = [
            # 标签
            EnemyTag(enemy_id=enemy_id, enemy_type=enemy_type, name=enemy_name),
            # 物理
            Position(x=x, y=y),
            Velocity(),
            Collider(width=float(sprite_w), height=float(sprite_h)),
            # 渲染
            Sprite(
                sprite_key=f"enemy_{enemy_id}_idle",
                width=sprite_w, height=sprite_h,
                color=sprite_color,
            ),
            Animation(current_anim="idle"),
            # 战斗属性
            Health(current=health_val, maximum=health_val),
            Stats(
                attack=attack_val,
                defense=defense_val,
                speed=speed_val,
                crit_rate=crit_rate,
                dodge_rate=dodge_rate,
            ),
            Block(),
            # 系统
            BuffList(),
            IntentDisplay(),
            # AI
            AIController(ai_pattern=enemy_config.get("ai_pattern", "melee_aggressive")),
            # 向后兼容
            Combat(
                attack=attack_val,
                defense=defense_val,
                speed=speed_val,
                crit_rate=crit_rate,
                dodge_rate=dodge_rate,
            ),
            Renderable(sprite_key=f"enemy_{enemy_id}_idle", layer=1),
        ]

        # 精英/BOSS 技能
        special_skills = enemy_config.get("special_skills", [])
        if special_skills:
            skill_set = SkillSet(skills=[
                SkillSlot(
                    skill_id=sk["id"],
                    description=sk.get("description", ""),
                    cooldown=float(sk.get("cooldown", 3.0)),
                )
                for sk in special_skills
            ])
            components.append(skill_set)

        # 掉落表
        drop_cfg = enemy_config.get("drop_table", {})
        if drop_cfg:
            components.append(DropTable(
                gold_min=drop_cfg.get("gold_min", 0),
                gold_max=drop_cfg.get("gold_max", 0),
                relic_drop_chance=drop_cfg.get("relic_drop_chance", 0.0),
                essence=drop_cfg.get("essence", 0),
                relic_choices=drop_cfg.get("relic_choices", 0),
            ))

        entity = self._world.create_entity(*components)
        return entity

    # ── BOSS 创建 ─────────────────────────────────────────────────────────

    def create_boss(self, boss_config: dict,
                    x: float = 800.0, y: float = 250.0) -> int:
        """
        根据 BOSS 配置创建 BOSS 实体。
        BOSS 使用 phases 定义多阶段行为。

        :param boss_config: config/enemies/bosses.yaml 中的单条 boss 节
                            必须包含 'id', 'phases' 字段
        :return: 实体 ID
        """
        boss_id = boss_config["id"]
        boss_name = boss_config.get("name", boss_id)
        phases_raw = boss_config.get("phases", [])

        # 从第一阶段获取基础属性 (或从 base_stats 如果有)
        base_stats = boss_config.get("base_stats", {})
        # BOSS 配置可能没有 base_stats，使用默认高数值
        health_val = base_stats.get("health", 500)
        attack_val = base_stats.get("attack", 20)
        defense_val = base_stats.get("defense", 10)
        speed_val = float(base_stats.get("speed", 5))

        # 构建阶段数据
        phases = []
        all_skills = []
        for phase_data in phases_raw:
            phase_skills = phase_data.get("skills", [])
            phases.append(BossPhaseData(
                phase=phase_data["phase"],
                hp_threshold=phase_data.get("hp_threshold", 1.0),
                description=phase_data.get("description", ""),
                skills=phase_skills,
            ))
            all_skills.extend(phase_skills)

        # 构建技能槽 (所有阶段技能合并)
        skill_slots = [
            SkillSlot(
                skill_id=sk["id"],
                description=sk.get("description", ""),
                cooldown=float(sk.get("cooldown", 3.0)),
            )
            for sk in all_skills
        ]

        # BOSS 精灵更大
        sprite_w, sprite_h = 96, 112

        # 掉落表
        drop_cfg = boss_config.get("drop_table", {})

        components = [
            # 标签
            EnemyTag(enemy_id=boss_id, enemy_type="boss", name=boss_name),
            # 物理
            Position(x=x, y=y),
            Velocity(),
            Collider(width=float(sprite_w), height=float(sprite_h)),
            # 渲染
            Sprite(
                sprite_key=f"boss_{boss_id}_idle",
                width=sprite_w, height=sprite_h,
                color=(180, 40, 40),  # 红色占位 (BOSS)
            ),
            Animation(current_anim="idle"),
            # 战斗
            Health(current=health_val, maximum=health_val),
            Stats(
                attack=attack_val,
                defense=defense_val,
                speed=speed_val,
            ),
            Block(),
            BuffList(),
            IntentDisplay(),
            # AI: BOSS 不用 AIController, 用 BossController
            BossController(
                phases=phases,
                current_phase=1,
                boss_name=boss_name,
            ),
            SkillSet(skills=skill_slots),
            # 掉落
            DropTable(
                gold_min=drop_cfg.get("gold_min", 100),
                gold_max=drop_cfg.get("gold_max", 200),
                essence=drop_cfg.get("essence", 3),
                relic_choices=drop_cfg.get("relic_choices", 3),
            ),
            # 向后兼容
            Combat(attack=attack_val, defense=defense_val, speed=speed_val),
            Renderable(sprite_key=f"boss_{boss_id}_idle", layer=1),
        ]

        entity = self._world.create_entity(*components)
        return entity

    # ── 内部辅助 ──────────────────────────────────────────────────────────

    @staticmethod
    def _enemy_sprite_params(enemy_type: str):
        """根据敌人类型返回 (width, height, color)"""
        if enemy_type == "elite":
            return 72, 90, (160, 80, 40)    # 橙色占位 (精英)
        elif enemy_type == "boss":
            return 96, 112, (180, 40, 40)   # 红色占位 (BOSS)
        else:
            return 56, 70, (80, 80, 100)    # 灰色占位 (普通)


# ═══════════════════════════════════════════════════════════════════════════════
# 向后兼容的模块级函数 (被 room_populator.py 等使用)
# ═══════════════════════════════════════════════════════════════════════════════

def create_player(world: "esper.World", char_config: dict,
                  x: float = 200.0, y: float = 400.0) -> int:
    """
    模块级便捷函数：根据角色配置创建玩家实体。
    内部委托给 EntityFactory。
    """
    factory = EntityFactory(world)
    return factory.create_player(char_config, x, y)


def create_enemy(world: "esper.World", enemy_config: dict,
                 x: float = 800.0, y: float = 300.0) -> int:
    """
    模块级便捷函数：根据敌人配置创建敌人实体。
    内部委托给 EntityFactory。
    """
    factory = EntityFactory(world)
    return factory.create_enemy(enemy_config, x, y)


def create_boss(world: "esper.World", boss_config: dict,
                x: float = 800.0, y: float = 250.0) -> int:
    """
    模块级便捷函数：根据 BOSS 配置创建 BOSS 实体。
    内部委托给 EntityFactory。
    """
    factory = EntityFactory(world)
    return factory.create_boss(boss_config, x, y)
