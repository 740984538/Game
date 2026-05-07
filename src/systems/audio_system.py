"""
音频系统 - 阶段 9-6（音效播放）/ 9-7（背景音乐）

设计要点：
- 单例 :class:`AudioSystem`，挂载到 Game 上为 ``game.audio``
- 通过事件总线订阅常用事件（按钮点击 / 卡牌打出 / 攻击 / 受伤 / 拾取等），
  各场景只需 ``event_manager.publish("on_card_played", ...)`` 即可触发音效
- 资源缺失时不抛异常，仅 logger.debug —— 方便在没有音频素材的开发期使用
- 背景音乐随场景切换：``play_bgm("main_menu")`` 自动加载
  ``assets/audio/bgm/main_menu.{ogg,wav,mp3}``，
  与当前 BGM 相同时不会重新播放（避免每次场景切换打断音乐）
"""
from __future__ import annotations

import logging
import os
from typing import Callable, Dict, Optional

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

# esper 兼容（旧 Processor 接口）
try:
    import esper
    _esper_available = True
except ImportError:
    _esper_available = False

from src.core.event_manager import event_manager
from src.utils.constants import ASSETS_DIR

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 事件 → 音效  默认映射
# ═══════════════════════════════════════════════════════════════════════════════

# 事件名 → 相对 audio/sfx/ 的文件名（不含扩展名，自动尝试 .ogg/.wav/.mp3）
DEFAULT_SFX_BINDINGS: Dict[str, str] = {
    # UI
    "ui_button_click":   "ui_click",
    "ui_button_hover":   "ui_hover",
    "ui_dialog_open":    "ui_open",
    # 卡牌
    "on_card_played":    "card_play",
    "on_card_drawn":     "card_draw",
    "on_card_discarded": "card_discard",
    # 战斗
    "on_attack":         "attack",
    "on_deal_damage":    "hit",
    "on_damaged":        "damage",
    "on_block":          "block",
    "on_crit":           "crit",
    "on_kill":           "kill",
    "on_death":          "death",
    # 经济 / 拾取
    "on_gold_changed":   "coin",
    "on_relic_pickup":   "pickup",
    # 战斗结算
    "on_battle_win":     "victory_small",
    "on_battle_lose":    "defeat",
}

# 场景名（GameState.name）→ BGM 文件名（相对 audio/bgm/）
SCENE_BGM: Dict[str, Optional[str]] = {
    "MAIN_MENU":         "main_menu",
    "CHARACTER_SELECT":  "main_menu",
    "MAP_NAVIGATION":    "map",
    "COMBAT":            "combat",
    "SHOP":              "shop",
    "EVENT":             "event",
    "REST":              "rest",
    "RELIC_SELECT":      "shop",
    "PAUSE":             None,            # 不切换
    "GAME_OVER":         "game_over",
    "VICTORY":           "victory",
    "SETTINGS":          None,
    "META_UPGRADE":      "main_menu",
    "CODEX":             "main_menu",
}

_AUDIO_EXTS = (".ogg", ".wav", ".mp3")


# ═══════════════════════════════════════════════════════════════════════════════
# AudioSystem
# ═══════════════════════════════════════════════════════════════════════════════

class AudioSystem:
    """音频管理器（单例，由 Game 持有一份引用为 ``game.audio``）。"""

    _instance: Optional["AudioSystem"] = None

    @classmethod
    def instance(cls) -> "AudioSystem":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance is not None:
            try:
                cls._instance.shutdown()
            except Exception:
                pass
        cls._instance = None

    def __init__(self) -> None:
        self._music_volume: float = 0.7
        self._sfx_volume:   float = 0.8
        self._sfx_bindings: Dict[str, str] = dict(DEFAULT_SFX_BINDINGS)
        self._handlers:     Dict[str, Callable] = {}
        self._subscribed:   bool = False
        self._current_bgm:  Optional[str] = None
        self._mixer_ready:  bool = False

        if _pygame_available:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                self._mixer_ready = pygame.mixer.get_init() is not None
            except Exception as exc:  # noqa: BLE001
                logger.warning("pygame.mixer 初始化失败 %s，音效将被忽略", exc)
                self._mixer_ready = False

        self._subscribe_events()

    # ── 事件订阅 ──────────────────────────────────

    def _subscribe_events(self) -> None:
        if self._subscribed:
            return
        for evt, sfx_key in self._sfx_bindings.items():
            handler = self._make_handler(sfx_key)
            self._handlers[evt] = handler
            event_manager.subscribe(evt, handler)
        self._subscribed = True

    def _unsubscribe_events(self) -> None:
        if not self._subscribed:
            return
        for evt, handler in self._handlers.items():
            try:
                event_manager.unsubscribe(evt, handler)
            except Exception:
                pass
        self._handlers.clear()
        self._subscribed = False

    def _make_handler(self, sfx_key: str) -> Callable:
        """为某个 sfx_key 生成一个事件处理函数（闭包捕获 key）"""
        def _handler(*args, **kwargs):
            self.play_sfx(sfx_key)
        return _handler

    # ── 公开 API ──────────────────────────────────

    def set_music_volume(self, vol: float) -> None:
        self._music_volume = max(0.0, min(1.0, float(vol)))
        if self._mixer_ready:
            try:
                pygame.mixer.music.set_volume(self._music_volume)
            except Exception:
                pass

    def set_sfx_volume(self, vol: float) -> None:
        self._sfx_volume = max(0.0, min(1.0, float(vol)))

    @property
    def music_volume(self) -> float:
        return self._music_volume

    @property
    def sfx_volume(self) -> float:
        return self._sfx_volume

    def play_sfx(self, key: str) -> None:
        """直接按文件名（不含扩展名，相对 audio/sfx/）播放音效。"""
        if not self._mixer_ready:
            return
        path = _resolve_audio("sfx", key)
        if not path:
            logger.debug("音效文件缺失: sfx/%s", key)
            return
        sound = _load_sound_cached(path)
        if sound is None:
            return
        try:
            sound.set_volume(self._sfx_volume)
            sound.play()
        except Exception as exc:  # noqa: BLE001
            logger.debug("播放音效失败 %s: %s", path, exc)

    def play_bgm(self, key: Optional[str], loops: int = -1, fade_ms: int = 400) -> None:
        """
        按 key 播放 BGM；与当前 BGM 相同时不重启。
        ``key=None`` 时不做任何操作（用于设置/暂停场景）。
        """
        if key is None or not self._mixer_ready:
            return
        if self._current_bgm == key and pygame.mixer.music.get_busy():
            return
        path = _resolve_audio("bgm", key)
        if not path:
            logger.debug("BGM 文件缺失: bgm/%s", key)
            self._current_bgm = key  # 仍然记录，避免每帧重试
            return
        try:
            pygame.mixer.music.fadeout(fade_ms)
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self._music_volume)
            pygame.mixer.music.play(loops)
            self._current_bgm = key
            logger.debug("播放 BGM: %s", path)
        except Exception as exc:  # noqa: BLE001
            logger.debug("播放 BGM 失败 %s: %s", path, exc)

    def play_bgm_for_state(self, state_name: str) -> None:
        """根据 GameState.name 切换 BGM"""
        if state_name in SCENE_BGM:
            self.play_bgm(SCENE_BGM[state_name])

    def stop_bgm(self) -> None:
        if self._mixer_ready:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        self._current_bgm = None

    def shutdown(self) -> None:
        self._unsubscribe_events()
        self.stop_bgm()


# ═══════════════════════════════════════════════════════════════════════════════
# 内部工具：路径解析与缓存
# ═══════════════════════════════════════════════════════════════════════════════

_audio_cache: Dict[str, "pygame.mixer.Sound"] = {}


def _resolve_audio(category: str, key: str) -> Optional[str]:
    """
    在 ``assets/audio/<category>/`` 下尝试 ``key.ogg``、``key.wav``、``key.mp3``。
    """
    base = os.path.join(ASSETS_DIR, "audio", category)
    for ext in _AUDIO_EXTS:
        path = os.path.join(base, f"{key}{ext}")
        if os.path.isfile(path):
            return path
    return None


def _load_sound_cached(path: str):
    if not _pygame_available:
        return None
    if path in _audio_cache:
        return _audio_cache[path]
    try:
        snd = pygame.mixer.Sound(path)
        _audio_cache[path] = snd
        return snd
    except Exception as exc:  # noqa: BLE001
        logger.debug("加载音效失败 %s: %s", path, exc)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# esper 处理器兼容（保留旧接口）
# ═══════════════════════════════════════════════════════════════════════════════

if _esper_available:
    class AudioProcessor(esper.Processor):  # type: ignore[misc]
        """ECS 兼容空处理器（音频实际通过事件总线 + AudioSystem 处理）"""

        def process(self, *args, **kwargs):
            return None
else:  # pragma: no cover - 仅在无 esper 时使用
    class AudioProcessor:  # type: ignore[no-redef]
        def process(self, *args, **kwargs):
            return None
