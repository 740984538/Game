"""
移动系统 - 对应文档 §10.3.2 / §6.2.1 战斗操作
处理所有具有 Position + Velocity 组件的实体移动
"""
from __future__ import annotations
from src.ecs.components import Position, Velocity, Collider
from src.utils.constants import SCREEN_WIDTH, SCREEN_HEIGHT

try:
    import esper
    class MovementProcessor(esper.Processor):
        """每帧根据速度向量更新坐标，并做边界约束"""
        def process(self, dt: float) -> None:
            for _ent, (pos, vel) in self.world.get_components(Position, Velocity):
                pos.x += vel.vx * dt
                pos.y += vel.vy * dt
                # 简单边界限制
                pos.x = max(0.0, min(SCREEN_WIDTH, pos.x))
                pos.y = max(0.0, min(SCREEN_HEIGHT, pos.y))
except ImportError:
    class MovementProcessor:  # type: ignore[no-redef]
        """esper 未安装时的占位符"""
        def process(self, dt: float) -> None:
            pass
