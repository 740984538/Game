"""
AI 系统 - 对应文档 §4.2 战斗房间设计
实现敌人行为状态机：idle → chase → attack → retreat
"""
from __future__ import annotations
from src.ecs.components import AIController, Position, Velocity, EnemyTag, PlayerTag
from src.utils.helpers import distance, normalize

try:
    import esper
    class AIProcessor(esper.Processor):
        def process(self, dt: float) -> None:
            # 获取玩家位置
            player_pos = None
            for _ent, (_, pos) in self.world.get_components(PlayerTag, Position):
                player_pos = pos
                break
            if player_pos is None:
                return

            for _ent, (ai, pos, vel) in self.world.get_components(AIController, Position, Velocity):
                dist = distance(pos.x, pos.y, player_pos.x, player_pos.y)
                if dist <= ai.detection_range:
                    if dist > ai.attack_range:
                        # 追击
                        dx, dy = normalize(player_pos.x - pos.x, player_pos.y - pos.y)
                        vel.vx = dx * 100.0
                        vel.vy = dy * 100.0
                        ai.state = "chase"
                    else:
                        vel.vx = 0.0
                        vel.vy = 0.0
                        ai.state = "attack"
                        # TODO: 触发攻击逻辑
                else:
                    vel.vx = 0.0
                    vel.vy = 0.0
                    ai.state = "idle"
except ImportError:
    class AIProcessor:  # type: ignore[no-redef]
        def process(self, dt: float) -> None:
            pass
