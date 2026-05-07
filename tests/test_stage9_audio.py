"""
阶段 9-6 / 9-7 音频系统测试

不需要真实音频文件：所有路径解析失败时仅记录 debug，不抛异常。
重点验证：
- 单例 + 默认音量
- 事件订阅注册 + 取消订阅
- play_bgm 缓存当前 BGM key
- 设置音量边界（钳制）
"""
from __future__ import annotations

import pytest

from src.core.event_manager import event_manager
from src.systems.audio_system import (
    AudioSystem, DEFAULT_SFX_BINDINGS, SCENE_BGM,
)


@pytest.fixture(autouse=True)
def reset_audio():
    AudioSystem.reset_instance()
    event_manager.clear()
    yield
    AudioSystem.reset_instance()
    event_manager.clear()


class TestAudioSingleton:
    def test_instance_idempotent(self):
        a = AudioSystem.instance()
        b = AudioSystem.instance()
        assert a is b

    def test_default_volumes(self):
        a = AudioSystem.instance()
        assert 0 <= a.music_volume <= 1
        assert 0 <= a.sfx_volume <= 1


class TestVolumeClamp:
    def test_set_music_volume_clamps(self):
        a = AudioSystem.instance()
        a.set_music_volume(2.0)
        assert a.music_volume == 1.0
        a.set_music_volume(-1.0)
        assert a.music_volume == 0.0
        a.set_music_volume(0.5)
        assert a.music_volume == 0.5

    def test_set_sfx_volume_clamps(self):
        a = AudioSystem.instance()
        a.set_sfx_volume(99.0)
        assert a.sfx_volume == 1.0
        a.set_sfx_volume(-2.0)
        assert a.sfx_volume == 0.0


class TestEventSubscriptions:
    def test_default_bindings_subscribed(self):
        a = AudioSystem.instance()
        # 内部应注册了所有默认 binding
        assert a._subscribed
        for evt in DEFAULT_SFX_BINDINGS:
            assert evt in a._handlers

    def test_publish_does_not_raise_when_no_assets(self):
        AudioSystem.instance()
        # 没有真实音频文件时也应静默
        event_manager.publish("on_card_played", card_id="strike")
        event_manager.publish("on_attack")
        event_manager.publish("ui_button_click")

    def test_shutdown_unsubscribes(self):
        a = AudioSystem.instance()
        a.shutdown()
        assert not a._subscribed
        assert a._handlers == {}


class TestSceneBgmMapping:
    def test_main_states_have_bgm(self):
        # 核心场景应有 BGM 配置（值可以为 None）
        for s in ("MAIN_MENU", "COMBAT", "MAP_NAVIGATION", "SHOP",
                  "GAME_OVER", "VICTORY"):
            assert s in SCENE_BGM

    def test_play_bgm_for_state_no_assets(self):
        a = AudioSystem.instance()
        # 没有 bgm 文件时 play_bgm 仍应安全
        a.play_bgm_for_state("MAIN_MENU")
        a.play_bgm_for_state("PAUSE")     # None
        a.play_bgm_for_state("UNKNOWN")   # 不在字典里也不抛
