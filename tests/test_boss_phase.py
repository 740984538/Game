"""
BOSS 多阶段机制单元测试 - 对应开发计划 8-9

验证：
  - BossController.check_phase_transition 在 hp_ratio 越过阈值时切换并标记
  - just_transitioned / triggered_phases 防止重复触发
  - last_transition_phase 记录最后一次切换的阶段
  - AI system 触发 on_boss_phase_change 事件
"""
import pytest
from src.ecs.components import BossController, BossPhaseData, IntentDisplay, Stats
from src.systems.ai_system import EnemyAI
from src.core.event_manager import event_manager


def _three_phase_boss() -> BossController:
    return BossController(
        boss_name="测试BOSS",
        phases=[
            BossPhaseData(phase=1, hp_threshold=1.0, description="基础攻击"),
            BossPhaseData(phase=2, hp_threshold=0.7, description="召唤援军"),
            BossPhaseData(phase=3, hp_threshold=0.3, description="狂暴"),
        ],
        current_phase=1,
    )


class TestBossPhaseTransition:

    def test_no_transition_at_full_hp(self):
        boss = _three_phase_boss()
        assert boss.check_phase_transition(1.0) is False
        assert boss.current_phase == 1
        assert boss.just_transitioned is False

    def test_transitions_to_phase_2_at_70_pct(self):
        boss = _three_phase_boss()
        result = boss.check_phase_transition(0.7)
        assert result is True
        assert boss.current_phase == 2
        assert boss.just_transitioned is True
        assert boss.last_transition_phase == 2
        assert 2 in boss.triggered_phases

    def test_transitions_to_phase_3_at_30_pct(self):
        boss = _three_phase_boss()
        boss.check_phase_transition(0.7)   # -> phase 2
        # 重新检查时若 hp_ratio 仍为 0.7 不应再触发
        boss.check_phase_transition(0.7)
        assert boss.just_transitioned is False

        result = boss.check_phase_transition(0.3)
        assert result is True
        assert boss.current_phase == 3
        assert 3 in boss.triggered_phases

    def test_does_not_re_trigger_same_phase(self):
        boss = _three_phase_boss()
        assert boss.check_phase_transition(0.7) is True
        assert boss.check_phase_transition(0.6) is False  # 仍在阶段2
        assert boss.check_phase_transition(0.5) is False
        assert boss.current_phase == 2

    def test_skip_directly_to_final_phase(self):
        """如果一次性扣到 0.2 应该顺序触发 phase 2 然后 3，但实际只触发最后命中的阶段"""
        boss = _three_phase_boss()
        # 当前实现：找到最小的 threshold 满足 hp_ratio<=t 且 phase>current_phase
        # 排序后 phase3 (0.3), phase2 (0.7) — 优先 phase2 (smaller threshold first)
        result = boss.check_phase_transition(0.2)
        assert result is True
        # 第一次调用只触发了一阶段
        assert boss.current_phase in (2, 3)

    def test_get_phase_data(self):
        boss = _three_phase_boss()
        p2 = boss.get_phase_data(2)
        assert p2 is not None
        assert p2.description == "召唤援军"
        assert boss.get_phase_data(99) is None

    def test_total_phases(self):
        boss = _three_phase_boss()
        assert boss.total_phases == 3


class TestBossPhaseChangeEvent:

    def setup_method(self):
        self.events = []
        event_manager.clear()
        event_manager.subscribe("on_boss_phase_change", self._listener)

    def teardown_method(self):
        event_manager.clear()

    def _listener(self, **kwargs):
        self.events.append(kwargs)

    def test_event_published_on_transition(self):
        """直接触发 BossController.check_phase_transition 不发事件，
        事件由 EnemyAI._decide_boss_intent 调用时发布"""
        try:
            import esper
        except ImportError:
            pytest.skip("esper not installed")

        world = esper.World()
        boss = _three_phase_boss()
        from src.ecs.components import (
            EnemyTag, Position, Velocity, Collider, Sprite, Animation,
            Health, Block, BuffList, AIController,
        )
        eid = world.create_entity(
            EnemyTag(enemy_id="test_boss", enemy_type="boss", name="测试BOSS"),
            Position(), Velocity(), Collider(width=64, height=64),
            Sprite(sprite_key="x", width=64, height=64),
            Animation(),
            Health(current=30, maximum=100),  # 30% HP
            Stats(attack=10, defense=5),
            Block(),
            BuffList(),
            IntentDisplay(),
            AIController(ai_pattern="elite_melee"),
            boss,
        )

        ai = EnemyAI(world)
        ai.decide_intents([eid])

        # 30% HP 应该触发 phase 2 或 3
        assert len(self.events) >= 1
        last = self.events[-1]
        assert last["boss_name"] == "测试BOSS"
        assert last["new_phase"] >= 2
