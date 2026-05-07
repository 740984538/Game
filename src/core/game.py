"""
游戏主循环
对应文档 §10.3.1 ECS架构、§8.1.1 帧率要求

阶段 9 集成：
- ``Game.audio``: 全局音频系统（阶段 9-6 / 9-7）
- ``Game.save_manager``: 全局存档管理器（阶段 9-2 / 9-3 / 9-5）
- 启动时应用持久化设置（音量、分辨率、全屏）-- 阶段 9-5
- 状态切换时自动播放对应场景 BGM -- 阶段 9-7
"""
from __future__ import annotations

import json
import logging
import os

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.core.state_machine import StateMachine
from src.core.event_manager import event_manager
from src.core.resource_manager import resource_manager
from src.core.run_state import RunStateManager
from src.data.save_manager import SaveManager
from src.systems.audio_system import AudioSystem
from src.utils.constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE, SAVE_DIR
from src.utils.enums import GameState

logger = logging.getLogger(__name__)


_RESOLUTIONS = [
    (1280, 720), (1366, 768), (1600, 900), (1920, 1080),
]
_DEFAULT_SETTINGS = {
    "music_volume":   0.7,
    "sound_volume":   0.8,
    "resolution_idx": 0,
    "fullscreen":     False,
}


class Game:
    """
    游戏主类，负责：
    1. 初始化 pygame、显示窗口、音频系统、存档管理器
    2. 应用持久化的玩家设置（音量 / 分辨率 / 全屏）
    3. 注册所有场景到状态机
    4. 驱动主循环（事件 → 更新 → 渲染）
    """

    def __init__(self) -> None:
        if not _pygame_available:
            raise RuntimeError("pygame 未安装，请执行 pip install pygame")

        # ── 应用持久化设置（阶段 9-5） ──
        self._settings = self._load_settings()
        flags = pygame.FULLSCREEN if self._settings["fullscreen"] else 0
        w, h = _RESOLUTIONS[self._settings["resolution_idx"]]
        self.screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.running = False

        # ── 跨场景共享状态 ──
        self.run_state = RunStateManager()

        # ── 全局服务（阶段 9-2/3/5/6/7） ──
        self.save_manager: SaveManager = SaveManager.instance()
        self.audio: AudioSystem = AudioSystem.instance()
        self.audio.set_music_volume(self._settings["music_volume"])
        self.audio.set_sfx_volume(self._settings["sound_volume"])

        # 提前预热元进度缓存
        self.meta_progress = self.save_manager.load_meta_progress()

        self.state_machine = StateMachine()
        self._register_scenes()
        # 状态切换时自动切 BGM
        self.state_machine.add_change_listener(self._on_state_changed)

    # ── 设置 ────────────────────────────────────────

    def _load_settings(self) -> dict:
        """从 saves/settings.json 读取玩家设置；不存在则使用默认值"""
        settings = dict(_DEFAULT_SETTINGS)
        path = os.path.join(SAVE_DIR, "settings.json")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                settings.update({k: data.get(k, v) for k, v in settings.items()})
            except Exception as exc:  # noqa: BLE001
                logger.warning("加载 settings.json 失败 %s，使用默认值", exc)
        # 索引兜底
        idx = settings.get("resolution_idx", 0)
        if not isinstance(idx, int) or idx < 0 or idx >= len(_RESOLUTIONS):
            settings["resolution_idx"] = 0
        return settings

    # ── 场景注册 ────────────────────────────────────

    def _register_scenes(self) -> None:
        """注册所有场景，延迟导入避免循环引用"""
        from src.scenes.main_menu_scene import MainMenuScene
        from src.scenes.character_select_scene import CharacterSelectScene
        from src.scenes.map_navigation_scene import MapNavigationScene
        from src.scenes.combat_scene import CombatScene
        from src.scenes.shop_scene import ShopScene
        from src.scenes.event_scene import EventScene
        from src.scenes.rest_scene import RestScene
        from src.scenes.relic_select_scene import RelicSelectScene
        from src.scenes.pause_scene import PauseScene
        from src.scenes.game_over_scene import GameOverScene
        from src.scenes.victory_scene import VictoryScene
        from src.scenes.settings_scene import SettingsScene
        from src.scenes.meta_upgrade_scene import MetaUpgradeScene
        from src.scenes.codex_scene import CodexScene

        self.state_machine.register(GameState.MAIN_MENU,         MainMenuScene(self))
        self.state_machine.register(GameState.CHARACTER_SELECT,  CharacterSelectScene(self))
        self.state_machine.register(GameState.MAP_NAVIGATION,    MapNavigationScene(self))
        self.state_machine.register(GameState.COMBAT,            CombatScene(self))
        self.state_machine.register(GameState.SHOP,              ShopScene(self))
        self.state_machine.register(GameState.EVENT,             EventScene(self))
        self.state_machine.register(GameState.REST,              RestScene(self))
        self.state_machine.register(GameState.RELIC_SELECT,      RelicSelectScene(self))
        self.state_machine.register(GameState.PAUSE,             PauseScene(self))
        self.state_machine.register(GameState.GAME_OVER,         GameOverScene(self))
        self.state_machine.register(GameState.VICTORY,           VictoryScene(self))
        self.state_machine.register(GameState.SETTINGS,          SettingsScene(self))
        self.state_machine.register(GameState.META_UPGRADE,      MetaUpgradeScene(self))
        self.state_machine.register(GameState.CODEX,             CodexScene(self))

        # 初始状态
        self.state_machine.change(GameState.MAIN_MENU)

    # ── 状态切换回调（阶段 9-7） ────────────────────

    def _on_state_changed(self, new_state: GameState) -> None:
        try:
            self.audio.play_bgm_for_state(new_state.name)
        except Exception as exc:  # noqa: BLE001
            logger.debug("切换 BGM 失败: %s", exc)

    # ── 主循环 ──────────────────────────────────────

    def run(self) -> None:
        """主循环"""
        self.running = True
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0  # 转换为秒

            # 全局事件处理（退出）
            for evt in pygame.event.get():
                if evt.type == pygame.QUIT:
                    self.running = False
                else:
                    self.state_machine.handle_event(evt)

            self.state_machine.update(dt)
            self.state_machine.render(self.screen)
            pygame.display.flip()

        # 退出前关闭存档与音频
        try:
            self.audio.shutdown()
        except Exception:
            pass
