"""
实体工厂
负责创建带有预设组件的游戏实体
对应文档 §10.3.1 ECS架构
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from src.ecs.components import (
    Position, Velocity, Health, Combat, Wallet,
    Renderable, Animation, PlayerTag, EnemyTag,
    AIController, CardHolder, RelicHolder, BuffList, Collider,
)

if TYPE_CHECKING:
    import esper


def create_player(world: "esper.World", char_config: dict, x: float, y: float) -> int:
    """
    根据角色配置创建玩家实体
    :param world: ECS世界
    :param char_config: config/characters/*.yaml 中的 character 节
    :param x, y: 初始坐标
    :return: 实体 ID
    """
    stats = char_config["base_stats"]
    entity = world.create_entity(
        PlayerTag(),
        Position(x=x, y=y),
        Velocity(),
        Collider(width=32, height=48),
        Health(current=stats["health"], maximum=stats["health"]),
        Combat(
            attack=stats["attack"],
            defense=stats["defense"],
            speed=float(stats["speed"]),
        ),
        Wallet(gold=char_config.get("starting_gold", 100)),
        Renderable(sprite_key=f"char_{char_config['id']}_idle", layer=1),
        Animation(current_anim="idle"),
        CardHolder(),
        RelicHolder(relic_ids=[char_config.get("starting_relic", "")]),
        BuffList(),
    )
    return entity


def create_enemy(world: "esper.World", enemy_config: dict, x: float, y: float) -> int:
    """
    根据敌人配置创建敌人实体
    :param world: ECS世界
    :param enemy_config: config/enemies/*.yaml 中的单条 enemy 节
    :param x, y: 初始坐标
    :return: 实体 ID
    """
    stats = enemy_config["base_stats"]
    entity = world.create_entity(
        EnemyTag(enemy_id=enemy_config["id"], enemy_type=enemy_config.get("type", "common")),
        Position(x=x, y=y),
        Velocity(),
        Collider(width=32, height=48),
        Health(current=stats["health"], maximum=stats["health"]),
        Combat(
            attack=stats["attack"],
            defense=stats["defense"],
            speed=float(stats["speed"]),
        ),
        AIController(ai_pattern=enemy_config.get("ai_pattern", "melee_aggressive")),
        Renderable(sprite_key=f"enemy_{enemy_config['id']}_idle", layer=1),
        Animation(current_anim="idle"),
        BuffList(),
    )
    return entity
