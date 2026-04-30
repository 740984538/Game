"""
资源管理器
统一管理图片、音频、字体的加载与缓存
对应开发计划 §3-1（资源管理器框架）、§3-2（图片加载）、§3-3（字体加载）

特性：
- 单例模式，全局唯一实例
- 懒加载 + LRU-like 缓存，避免重复 I/O
- 图片不存在时自动返回可配置尺寸的占位图
- 字体支持系统字体与 assets/fonts/ 自定义字体（.ttf / .otf）
- 字体回退链：自定义文件 → 同名系统字体 → 通用中文系统字体 → pygame 默认字体
- 音效/音乐统一管理
"""
from __future__ import annotations

import os
import logging
from typing import Dict, Optional, Tuple

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.utils.constants import ASSETS_DIR

logger = logging.getLogger(__name__)

# 占位图默认尺寸与颜色
_PLACEHOLDER_SIZE: Tuple[int, int] = (64, 64)
_PLACEHOLDER_COLOR: Tuple[int, int, int] = (200, 0, 200)   # 紫红色，易于发现缺失资源


class ResourceManager:
    """
    懒加载 + 缓存资源管理器（单例）。

    使用方式::

        from src.core.resource_manager import ResourceManager
        rm = ResourceManager.instance()
        img = rm.get_image("ui/button.png")          # 直接按路径获取
        font = rm.get_font("default", size=16)       # 字体
    """

    _instance: Optional["ResourceManager"] = None

    # ── 单例访问 ────────────────────────────────────

    @classmethod
    def instance(cls) -> "ResourceManager":
        """返回全局唯一实例，不存在时自动创建。"""
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance._init_caches()
        return cls._instance

    def __init__(self) -> None:
        # 防止直接调用 __init__ 绕过单例
        # 如果已通过 instance() 初始化则跳过
        if not hasattr(self, "_images"):
            self._init_caches()

    def _init_caches(self) -> None:
        """初始化所有内部缓存字典。"""
        self._images: Dict[str, "pygame.Surface"] = {}
        self._sounds: Dict[str, "pygame.mixer.Sound"] = {}
        # 字体缓存 key = (path_or_name, size)
        self._fonts: Dict[Tuple[str, int], "pygame.font.Font"] = {}
        # 占位图缓存 key = (width, height, color)
        self._placeholders: Dict[Tuple, "pygame.Surface"] = {}
        # 音乐路径缓存 key = 自定义key, value = 绝对路径字符串
        self._music_paths: Dict[str, str] = {}

    # ── 工具 ────────────────────────────────────────

    @staticmethod
    def _abs(relative_path: str) -> str:
        """将相对于 assets/ 的路径转为绝对路径。"""
        return os.path.join(ASSETS_DIR, relative_path)

    # ── 图片 ────────────────────────────────────────

    def get_image(
        self,
        path: str,
        convert_alpha: bool = True,
        placeholder_size: Tuple[int, int] = _PLACEHOLDER_SIZE,
        placeholder_color: Tuple[int, int, int] = _PLACEHOLDER_COLOR,
    ) -> "pygame.Surface":
        """
        从 ``assets/images/<path>`` 加载图片并缓存。

        - 同一 path 第二次调用直接返回缓存，无 I/O。
        - 文件不存在时返回占位图（紫红色矩形），并记录 WARNING。

        Args:
            path: 相对于 ``assets/images/`` 的文件路径，如 ``"ui/button.png"``。
            convert_alpha: 是否以 alpha 模式转换表面（含透明通道的 PNG 建议为 True）。
            placeholder_size: 占位图尺寸，默认 64×64。
            placeholder_color: 占位图颜色，默认紫红色。

        Returns:
            pygame.Surface —— 成功时为实际图片，失败时为占位图。
        """
        if path in self._images:
            return self._images[path]

        if not _pygame_available:
            return self._make_placeholder(placeholder_size, placeholder_color)

        full_path = os.path.join(ASSETS_DIR, "images", path)
        if not os.path.isfile(full_path):
            logger.warning("图片不存在，返回占位图: %s", full_path)
            surf = self._make_placeholder(placeholder_size, placeholder_color)
            self._images[path] = surf
            return surf

        try:
            surface = pygame.image.load(full_path)
            surface = surface.convert_alpha() if convert_alpha else surface.convert()
            self._images[path] = surface
            logger.debug("加载图片成功: %s", full_path)
            return surface
        except Exception as exc:  # noqa: BLE001
            logger.error("加载图片失败 %s: %s", full_path, exc)
            surf = self._make_placeholder(placeholder_size, placeholder_color)
            self._images[path] = surf
            return surf

    def load_image(
        self,
        key: str,
        path: str,
        convert_alpha: bool = True,
    ) -> None:
        """
        兼容旧接口：预加载图片并以 *key* 存入缓存。

        与 :meth:`get_image` 不同，此方法使用自定义 key，
        之后用 :meth:`get_image_by_key` 取回。
        """
        if key in self._images:
            return
        if not _pygame_available:
            return
        full_path = self._abs(path)
        if not os.path.isfile(full_path):
            logger.warning("load_image: 文件不存在 %s", full_path)
            return
        try:
            surface = pygame.image.load(full_path)
            self._images[key] = surface.convert_alpha() if convert_alpha else surface.convert()
            logger.debug("load_image 成功: key=%s path=%s", key, full_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("load_image 失败 %s: %s", full_path, exc)

    def get_image_by_key(self, key: str) -> Optional["pygame.Surface"]:
        """返回通过 :meth:`load_image` 预加载的图片，不存在返回 None。"""
        return self._images.get(key)

    def _make_placeholder(
        self,
        size: Tuple[int, int] = _PLACEHOLDER_SIZE,
        color: Tuple[int, int, int] = _PLACEHOLDER_COLOR,
    ) -> "pygame.Surface":
        """
        生成（并缓存）一张纯色占位图。

        占位图上额外画一个 X 形交叉线，方便调试时快速识别。
        """
        cache_key = (size[0], size[1], color[0], color[1], color[2])
        if cache_key in self._placeholders:
            return self._placeholders[cache_key]

        if not _pygame_available:
            # 无 pygame 环境，返回空对象占位
            return object()  # type: ignore[return-value]

        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((*color, 180))  # 半透明填充
        # 画 X 标记，帮助开发者识别缺失资源
        w, h = size
        pygame.draw.line(surf, (255, 255, 255), (0, 0), (w - 1, h - 1), 2)
        pygame.draw.line(surf, (255, 255, 255), (w - 1, 0), (0, h - 1), 2)
        self._placeholders[cache_key] = surf
        return surf

    # ── 字体 ────────────────────────────────────────

    # 支持的自定义字体扩展名，按优先级排列
    _FONT_EXTENSIONS = (".ttf", ".otf")

    # 中文通用系统字体回退链（跨平台）
    _CJK_SYSTEM_FONTS = [
        "microsoftyahei",   # Windows：微软雅黑
        "simsun",           # Windows：宋体
        "notosanscjk",      # Linux：Noto Sans CJK
        "wqycjkzen",        # Linux：文泉驿
        "pingfang sc",      # macOS：苹方
        "heiti sc",         # macOS：黑体-简
    ]

    def get_font(
        self,
        name: str = "default",
        size: int = 16,
        system_fallback: Optional[str] = None,
    ) -> "pygame.font.Font":
        """
        获取字体（带缓存）。

        回退链：
        1. ``assets/fonts/<name>.ttf`` 或 ``assets/fonts/<name>.otf``
        2. ``assets/fonts/<name>``（name 本身含扩展名的完整路径）
        3. 同名系统字体（``pygame.font.SysFont(name, size)``）
        4. *system_fallback* 指定的系统字体（若传入）
        5. CJK 通用系统字体（微软雅黑 / Noto 等）
        6. pygame 内置默认字体

        Args:
            name: 字体名称（不含扩展名）或相对于 ``assets/fonts/`` 的完整文件名。
                  也可以是系统字体名称（如 ``"arial"``、``"microsoftyahei"``）。
            size: 字号（像素）。
            system_fallback: 额外的系统字体回退名称，默认 None。

        Returns:
            pygame.font.Font —— 永远不为 None，最差返回 pygame 默认字体。
        """
        cache_key = (name, size)
        if cache_key in self._fonts:
            return self._fonts[cache_key]

        if not _pygame_available:
            return None  # type: ignore[return-value]

        font: Optional["pygame.font.Font"] = None
        fonts_dir = os.path.join(ASSETS_DIR, "fonts")

        # 1. 尝试从 assets/fonts/ 加载自定义字体文件
        for ext in self._FONT_EXTENSIONS:
            candidate = os.path.join(fonts_dir, f"{name}{ext}")
            if os.path.isfile(candidate):
                try:
                    font = pygame.font.Font(candidate, size)
                    logger.debug("加载自定义字体(.%s): %s (size=%d)", ext.lstrip("."), candidate, size)
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.warning("加载自定义字体失败 %s: %s", candidate, exc)

        # 2. name 本身可能已包含扩展名（完整文件名）
        if font is None:
            candidate = os.path.join(fonts_dir, name)
            if os.path.isfile(candidate):
                try:
                    font = pygame.font.Font(candidate, size)
                    logger.debug("加载自定义字体(完整路径): %s (size=%d)", candidate, size)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("加载自定义字体失败 %s: %s", candidate, exc)

        # 3. 尝试同名系统字体
        if font is None:
            try:
                font = pygame.font.SysFont(name, size)
                # SysFont 找不到时返回默认字体而非 None，需通过 get_fonts() 验证
                sys_fonts = pygame.font.get_fonts()
                if name.lower().replace(" ", "") not in sys_fonts:
                    logger.debug("系统字体 '%s' 不存在，将继续回退", name)
                    font = None
                else:
                    logger.debug("使用系统字体: %s (size=%d)", name, size)
            except Exception as exc:  # noqa: BLE001
                logger.warning("SysFont(%s) 失败: %s", name, exc)
                font = None

        # 4. 尝试调用方指定的 system_fallback
        if font is None and system_fallback:
            try:
                font = pygame.font.SysFont(system_fallback, size)
                logger.debug("使用回退系统字体: %s (size=%d)", system_fallback, size)
            except Exception as exc:  # noqa: BLE001
                logger.warning("回退字体 SysFont(%s) 失败: %s", system_fallback, exc)
                font = None

        # 5. 尝试 CJK 通用系统字体（支持中文）
        if font is None:
            sys_fonts = pygame.font.get_fonts()
            for cjk_name in self._CJK_SYSTEM_FONTS:
                if cjk_name.replace(" ", "") in sys_fonts:
                    try:
                        font = pygame.font.SysFont(cjk_name, size)
                        logger.debug("使用 CJK 回退字体: %s (size=%d)", cjk_name, size)
                        break
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("CJK 字体 %s 失败: %s", cjk_name, exc)

        # 6. 最终回退：pygame 内置默认字体
        if font is None:
            font = pygame.font.Font(None, size)
            logger.warning("所有字体回退均失败，使用 pygame 默认字体 (size=%d)", size)

        self._fonts[cache_key] = font
        return font

    def get_font_path(self, name: str) -> Optional[str]:
        """
        返回 assets/fonts/ 下 *name* 字体文件的绝对路径（.ttf 优先于 .otf）。

        找不到时返回 None。
        """
        fonts_dir = os.path.join(ASSETS_DIR, "fonts")
        for ext in self._FONT_EXTENSIONS:
            candidate = os.path.join(fonts_dir, f"{name}{ext}")
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)
        # name 本身含扩展名
        candidate = os.path.join(fonts_dir, name)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
        return None

    def list_custom_fonts(self) -> list:
        """
        列出 assets/fonts/ 目录下所有可用的自定义字体文件名（含扩展名）。

        Returns:
            list[str] —— 文件名列表，如 ``["NotoSansSC.ttf", "pixel.otf"]``
        """
        fonts_dir = os.path.join(ASSETS_DIR, "fonts")
        if not os.path.isdir(fonts_dir):
            return []
        result = []
        for fname in sorted(os.listdir(fonts_dir)):
            if any(fname.lower().endswith(ext) for ext in self._FONT_EXTENSIONS):
                result.append(fname)
        return result

    def load_font(self, key: str, path: str, size: int) -> None:
        """
        兼容旧接口：预加载字体并以 *(key, size)* 存入缓存。

        path 相对于 ASSETS_DIR（如 ``"fonts/my_font.ttf"``）。
        若文件不存在则回退到 pygame 默认字体。
        """
        cache_key = (key, size)
        if cache_key in self._fonts:
            return
        if not _pygame_available:
            return
        full_path = self._abs(path)
        if os.path.isfile(full_path):
            try:
                self._fonts[cache_key] = pygame.font.Font(full_path, size)
                logger.debug("load_font 成功: key=%s path=%s size=%d", key, full_path, size)
                return
            except Exception as exc:  # noqa: BLE001
                logger.error("load_font 失败 %s: %s", full_path, exc)
        # 回退：使用 get_font 的回退链
        self._fonts[cache_key] = self.get_font(key, size)

    def get_font_by_key(self, key: str, size: int) -> Optional["pygame.font.Font"]:
        """返回通过 :meth:`load_font` 预加载的字体，不存在返回 None。"""
        return self._fonts.get((key, size))

    # ── 音效 ────────────────────────────────────────

    def get_sound(self, path: str) -> Optional["pygame.mixer.Sound"]:
        """
        从 ``assets/audio/<path>`` 加载音效并缓存。

        文件不存在时返回 None 并记录 WARNING（不抛异常）。
        """
        if path in self._sounds:
            return self._sounds[path]

        if not _pygame_available:
            return None

        full_path = os.path.join(ASSETS_DIR, "audio", path)
        if not os.path.isfile(full_path):
            logger.warning("音效不存在: %s", full_path)
            return None

        try:
            sound = pygame.mixer.Sound(full_path)
            self._sounds[path] = sound
            logger.debug("加载音效成功: %s", full_path)
            return sound
        except Exception as exc:  # noqa: BLE001
            logger.error("加载音效失败 %s: %s", full_path, exc)
            return None

    def load_sound(self, key: str, path: str) -> None:
        """兼容旧接口：预加载音效，以 key 存入缓存。path 相对于 ASSETS_DIR。"""
        if key in self._sounds:
            return
        if not _pygame_available:
            return
        full_path = self._abs(path)
        if not os.path.isfile(full_path):
            logger.warning("load_sound: 文件不存在 %s", full_path)
            return
        try:
            self._sounds[key] = pygame.mixer.Sound(full_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("load_sound 失败 %s: %s", full_path, exc)

    # ── 背景音乐 ────────────────────────────────────

    def play_music(self, path: str, loops: int = -1, volume: float = 0.7) -> None:
        """
        播放背景音乐。

        path 相对于 ``assets/audio/``。
        """
        if not _pygame_available:
            return
        full_path = os.path.join(ASSETS_DIR, "audio", path)
        if not os.path.isfile(full_path):
            logger.warning("背景音乐不存在: %s", full_path)
            return
        try:
            pygame.mixer.music.load(full_path)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
            pygame.mixer.music.play(loops)
        except Exception as exc:  # noqa: BLE001
            logger.error("播放背景音乐失败 %s: %s", full_path, exc)

    def load_music(self, key: str, path: str) -> None:
        """
        兼容旧接口：将音乐文件路径以 key 存入缓存（并不立即加载到 mixer，
        播放时再调用 :meth:`play_music_by_key`）。

        path 相对于 ASSETS_DIR（如 ``"audio/bgm/bgm_floor1.ogg"``）。
        """
        # 音乐文件不预解码，只记录路径供后续 play 使用
        # _sounds 缓存 key→路径字符串；实际 Sound 对象仅在需要时创建
        if key not in self._music_paths:
            full_path = self._abs(path)
            if os.path.isfile(full_path):
                self._music_paths[key] = full_path
                logger.debug("load_music 注册: key=%s path=%s", key, full_path)
            else:
                logger.warning("load_music: 文件不存在 %s", full_path)

    def play_music_by_key(self, key: str, loops: int = -1, volume: float = 0.7) -> None:
        """
        播放通过 :meth:`load_music` 注册的背景音乐。
        key 不存在时记录 WARNING 并忽略。
        """
        if not _pygame_available:
            return
        path = self._music_paths.get(key)
        if path is None:
            logger.warning("play_music_by_key: 未找到 key=%s，请先调用 load_music", key)
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
            pygame.mixer.music.play(loops)
            logger.debug("play_music_by_key: key=%s path=%s", key, path)
        except Exception as exc:  # noqa: BLE001
            logger.error("play_music_by_key 播放失败 key=%s: %s", key, exc)

    def get_sound_by_key(self, key: str) -> Optional["pygame.mixer.Sound"]:
        """返回通过 :meth:`load_sound` 预加载的音效，不存在返回 None。"""
        return self._sounds.get(key)

    def stop_music(self) -> None:
        """停止背景音乐。"""
        if _pygame_available:
            pygame.mixer.music.stop()

    # ── 缓存管理 ────────────────────────────────────

    def clear_images(self) -> None:
        """清空图片缓存（换场景时可选用）。"""
        self._images.clear()
        self._placeholders.clear()

    def clear_sounds(self) -> None:
        """清空音效缓存。"""
        self._sounds.clear()
        self._music_paths.clear()

    def clear(self) -> None:
        """清空所有资源缓存。"""
        self.clear_images()
        self.clear_sounds()
        # 字体通常跨场景复用，不清空

    def preload_images(self, paths: list) -> None:
        """
        批量预加载图片（paths 均相对于 ``assets/images/``）。

        调用后这些图片已在缓存中，游戏运行时无卡顿。
        """
        for path in paths:
            self.get_image(path)

    @property
    def image_cache_size(self) -> int:
        """当前已缓存的图片数量。"""
        return len(self._images)

    @property
    def sound_cache_size(self) -> int:
        """当前已缓存的音效数量。"""
        return len(self._sounds)

    @property
    def font_cache_size(self) -> int:
        """当前已缓存的字体数量。"""
        return len(self._fonts)


# ── 全局单例快捷访问 ─────────────────────────────────
# 保持向后兼容：原代码中 `from src.core.resource_manager import resource_manager` 仍可用
resource_manager: ResourceManager = ResourceManager.instance()
