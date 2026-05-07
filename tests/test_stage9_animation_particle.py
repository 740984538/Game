"""
阶段 9-8 / 9-9 动画 + 粒子系统 单元测试
"""
import math
import pytest

from src.utils.animation import (
    Easing, Tween, FloatingNumber, FloatingNumberManager, ScreenShake,
)
from src.utils.particle import Particle, ParticleSystem


# ── Easing ────────────────────────────────────────

class TestEasing:
    def test_endpoints_consistent(self):
        for fn in (Easing.linear, Easing.ease_in, Easing.ease_out,
                   Easing.ease_in_out, Easing.ease_out_cubic):
            assert fn(0.0) == pytest.approx(0.0, abs=0.01)
            assert fn(1.0) == pytest.approx(1.0, abs=0.01)

    def test_monotonic(self):
        prev = -1
        for i in range(11):
            t = i / 10.0
            cur = Easing.ease_in_out(t)
            assert cur >= prev - 1e-6
            prev = cur


# ── Tween ──────────────────────────────────────────

class TestTween:
    def test_scalar_progress(self):
        tw = Tween(start=0.0, end=10.0, duration=1.0)
        assert tw.value == pytest.approx(0.0)
        tw.update(0.5)
        assert tw.value == pytest.approx(5.0, abs=0.01)
        assert not tw.finished
        tw.update(0.6)
        assert tw.value == pytest.approx(10.0)
        assert tw.finished

    def test_tuple_value(self):
        tw = Tween(start=(0, 0), end=(100, 50), duration=1.0)
        tw.update(0.5)
        x, y = tw.value
        assert 49 <= x <= 51
        assert 24 <= y <= 26

    def test_on_complete_called_once(self):
        calls = []
        tw = Tween(0.0, 1.0, duration=0.1, on_complete=lambda: calls.append(1))
        tw.update(0.2)
        tw.update(0.5)
        assert calls == [1]

    def test_easing_applied(self):
        tw = Tween(0.0, 100.0, duration=1.0, easing=Easing.ease_out)
        tw.update(0.5)
        # ease_out at 0.5 = 0.75
        assert tw.value == pytest.approx(75.0, abs=0.01)

    def test_delay(self):
        tw = Tween(0.0, 1.0, duration=0.1, delay=0.5)
        tw.update(0.4)
        assert tw.value == pytest.approx(0.0)
        tw.update(0.2)   # past delay, half-way through
        assert tw.value > 0


# ── FloatingNumber ────────────────────────────────

class TestFloatingNumber:
    def test_alive_until_duration(self):
        f = FloatingNumber("10", 100, 100, duration=1.0)
        assert f.alive
        f.update(0.5)
        assert f.alive
        f.update(0.6)
        assert not f.alive

    def test_alpha_fades_after_half_duration(self):
        f = FloatingNumber("10", 0, 0, duration=1.0)
        f.update(0.4)
        assert f.alpha == 255
        f.update(0.4)
        assert f.alpha < 255

    def test_offset_y_increases(self):
        f = FloatingNumber("10", 0, 0, duration=1.0, rise=40.0)
        before = f.offset_y
        f.update(0.5)
        assert f.offset_y > before


class TestFloatingNumberManager:
    def test_spawn_and_age_out(self):
        m = FloatingNumberManager()
        m.spawn_damage(15, 100, 100)
        m.spawn_heal(10, 100, 200)
        assert len(m) == 2
        m.update(2.0)   # 全部过期
        assert len(m) == 0

    def test_clear(self):
        m = FloatingNumberManager()
        m.spawn_damage(1, 0, 0)
        m.spawn_heal(2, 0, 0)
        m.clear()
        assert len(m) == 0

    def test_crit_styling(self):
        m = FloatingNumberManager()
        f = m.spawn_damage(50, 0, 0, crit=True)
        assert f.crit
        assert f.color == (255, 200, 0)


# ── ScreenShake ───────────────────────────────────

class TestScreenShake:
    def test_no_shake_initially(self):
        s = ScreenShake()
        assert not s.is_shaking
        assert s.offset == (0, 0)

    def test_trigger_then_decays(self):
        s = ScreenShake()
        s.trigger(intensity=10.0, duration=0.2)
        assert s.is_shaking
        s.update(0.05)
        assert s.is_shaking
        s.update(0.5)
        assert not s.is_shaking
        assert s.offset == (0, 0)

    def test_stop_clears_state(self):
        s = ScreenShake()
        s.trigger(8.0, 1.0)
        s.update(0.1)
        s.stop()
        assert not s.is_shaking
        assert s.offset == (0, 0)


# ── ParticleSystem ────────────────────────────────

class TestParticle:
    def test_lifecycle(self):
        p = Particle(x=0, y=0, vx=10, vy=0, color=(255, 0, 0),
                     size=4, lifespan=1.0)
        p.update(0.5)
        assert p.x == pytest.approx(5.0)
        assert p.alive
        assert 100 < p.alpha < 200
        p.update(0.6)
        assert not p.alive

    def test_gravity(self):
        p = Particle(0, 0, 0, 0, (0, 0, 0), 1, 1.0, gravity=100)
        p.update(0.5)
        assert p.vy == pytest.approx(50.0)


class TestParticleSystem:
    def test_emit_attack_creates_particles(self):
        ps = ParticleSystem()
        ps.emit_attack(100, 100)
        assert len(ps) > 0

    def test_update_kills_old(self):
        ps = ParticleSystem()
        ps.emit_heal(0, 0)
        before = len(ps)
        assert before > 0
        ps.update(5.0)   # 远超 lifespan
        assert len(ps) == 0

    def test_max_particles_cap(self):
        ps = ParticleSystem()
        # 远超上限
        for _ in range(200):
            ps.emit(0, 0, count=20)
        assert len(ps) <= ParticleSystem.MAX_PARTICLES

    def test_clear(self):
        ps = ParticleSystem()
        ps.emit_pickup(0, 0)
        ps.clear()
        assert len(ps) == 0
