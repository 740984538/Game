"""
资源管理器
统一管理图片、音频、字体的加载与缓存
对应文档 §8.1.2 加载时间要求
"""
from __future__ import annotations
import os
from typing import Dict, Optional

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.utils.constants import ASSETS_DIR


class ResourceManager:
    """
    懒加载 + 缓存资源管理器。
    所有资源通过 key 索引，避免重复加载。
    """

    def __init__(self) -> None:
        self._images: Dict[str, object] = {}
        self._sounds: Dict[str, object] = {}
        self._fonts: Dict[str, object] = {}
        self._music_path: Optional[str] = None

    # ── 图片 ───────────────────────────────────────

    def load_image(self, key: str, path: str, convert_alpha: bool = True) -> None:
        """预加载图片到缓存"""
        if not _pygame_available:
            return
        full_path = os.path.join(ASSETS_DIR, path)
        if not os.path.exists(full_path):
            return
        surface = pygame.image.load(full_path)
        self._images[key] = surface.convert_alpha() if convert_alpha else surface.convert()

    def get_image(self, key: str) -> Optional[object]:
        """获取缓存中的图片，不存在返回 None"""
        return self._images.get(key)

    # ── 音效 ───────────────────────────────────────

    def load_sound(self, key: str, path: str) -> None:
        """预加载音效"""
        if not _pygame_available:
            return
        full_path = os.path.join(ASSETS_DIR, path)
        if not os.path.exists(full_path):
            return
        self._sounds[key] = pygame.mixer.Sound(full_path)

    def get_sound(self, key: str) -> Optional[object]:
        return self._sounds.get(key)

    # ── 字体 ───────────────────────────────────────

    def load_font(self, key: str, path: str, size: int) -> None:
        """预加载字体"""
        if not _pygame_available:
            return
        full_path = os.path.join(ASSETS_DIR, path)
        if os.path.exists(full_path):
            self._fonts[key] = pygame.font.Font(full_path, size)
        else:
            self._fonts[key] = pygame.font.SysFont("arial", size)

    def get_font(self, key: str) -> Optional[object]:
        return self._fonts.get(key)

    # ── 背景音乐 ───────────────────────────────────

    def play_music(self, path: str, loops: int = -1, volume: float = 0.7) -> None:
        """播放背景音乐"""
        if not _pygame_available:
            return
        full_path = os.path.join(ASSETS_DIR, path)
        if not os.path.exists(full_path):
            return
        pygame.mixer.music.load(full_path)
        pygame.mixer.music.set_volume(volume)
        pygame.mixer.music.play(loops)

    def stop_music(self) -> None:
        if _pygame_available:
            pygame.mixer.music.stop()

    def clear(self) -> None:
        """清空所有缓存（换场景时可选用）"""
        self._images.clear()
        self._sounds.clear()


# 全局单例
resource_manager = ResourceManager()
