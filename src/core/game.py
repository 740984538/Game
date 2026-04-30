"""
游戏主循环
对应文档 §10.3.1 ECS架构、§8.1.1 帧率要求
"""
from __future__ import annotations

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.core.state_machine import StateMachine
from src.core.event_manager import event_manager
from src.core.resource_manager import resource_manager
from src.utils.constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE
from src.utils.enums import GameState


class Game:
    """
    游戏主类，负责：
    1. 初始化 pygame 和显示窗口
    2. 注册所有场景到状态机
    3. 驱动主循环（事件 → 更新 → 渲染）
    """

    def __init__(self) -> None:
        if not _pygame_available:
            raise RuntimeError("pygame 未安装，请执行 pip install pygame")

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.running = False

        self.state_machine = StateMachine()
        self._register_scenes()

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

        self.state_machine.register(GameState.MAIN_MENU,         MainMenuScene(self))
        self.state_machine.register(GameState.CHARACTER_SELECT,   CharacterSelectScene(self))
        self.state_machine.register(GameState.MAP_NAVIGATION,     MapNavigationScene(self))
        self.state_machine.register(GameState.COMBAT,             CombatScene(self))
        self.state_machine.register(GameState.SHOP,               ShopScene(self))
        self.state_machine.register(GameState.EVENT,              EventScene(self))
        self.state_machine.register(GameState.REST,               RestScene(self))
        self.state_machine.register(GameState.RELIC_SELECT,       RelicSelectScene(self))
        self.state_machine.register(GameState.PAUSE,              PauseScene(self))
        self.state_machine.register(GameState.GAME_OVER,          GameOverScene(self))
        self.state_machine.register(GameState.VICTORY,            VictoryScene(self))
        self.state_machine.register(GameState.SETTINGS,           SettingsScene(self))

        # 初始状态
        self.state_machine.change(GameState.MAIN_MENU)

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
