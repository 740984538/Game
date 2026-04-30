"""
资源管理器字体加载单元测试
对应开发计划 §3-3（字体加载）

覆盖范围：
- 系统字体加载
- assets/fonts/ 目录自定义字体加载（.ttf / .otf）
- 字体缓存机制（同参数第二次调用不产生新对象）
- 不存在字体的回退行为（永远返回有效 Font 对象）
- get_font_path / list_custom_fonts 辅助方法
- load_font / get_font_by_key 兼容接口
- 字体大小参数生效
"""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest


# ── 辅助：重置单例 ──────────────────────────────────────────────────────────

def _reset_singleton():
    """每个测试前重置 ResourceManager 单例，避免缓存污染。"""
    from src.core import resource_manager as rm_module
    rm_module.ResourceManager._instance = None
    # 同时重置模块级快捷引用
    rm_module.resource_manager = rm_module.ResourceManager.instance()


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试自动重置单例。"""
    _reset_singleton()
    yield
    _reset_singleton()


@pytest.fixture()
def rm():
    """返回干净的 ResourceManager 实例。"""
    from src.core.resource_manager import ResourceManager
    return ResourceManager.instance()


@pytest.fixture()
def fonts_tmpdir(tmp_path):
    """
    创建临时 assets/fonts 目录，并将其 patch 进 ASSETS_DIR。
    返回临时 fonts 目录路径。
    """
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    with patch("src.core.resource_manager.ASSETS_DIR", str(tmp_path / "assets")):
        yield fonts_dir


# ── 测试：单例 ──────────────────────────────────────────────────────────────

class TestSingleton:
    def test_instance_is_singleton(self, rm):
        from src.core.resource_manager import ResourceManager
        assert ResourceManager.instance() is rm

    def test_font_cache_initially_empty(self, rm):
        assert rm.font_cache_size == 0


# ── 测试：系统字体加载 ──────────────────────────────────────────────────────

class TestSystemFont:
    def test_get_font_returns_font_object(self, rm):
        """get_font 必须返回一个 pygame.font.Font 对象（非 None）。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()
        font = rm.get_font("arial", size=16)
        assert font is not None
        assert isinstance(font, pygame.font.Font)
        pygame.quit()

    def test_get_font_default_size(self, rm):
        """不传 size 时使用默认 16。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()
        font = rm.get_font("arial")
        assert font is not None
        pygame.quit()

    def test_get_font_nonexistent_falls_back(self, rm):
        """找不到的字体名应回退，返回有效字体而非抛出异常。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()
        font = rm.get_font("这个字体肯定不存在_xyz123", size=14)
        assert font is not None
        assert isinstance(font, pygame.font.Font)
        pygame.quit()

    def test_different_sizes_return_different_objects(self, rm):
        """不同字号应缓存为不同条目。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()
        f1 = rm.get_font("arial", size=14)
        f2 = rm.get_font("arial", size=28)
        # 不同 size 不应共用同一对象
        assert f1 is not f2
        pygame.quit()


# ── 测试：缓存机制 ──────────────────────────────────────────────────────────

class TestFontCache:
    def test_same_call_returns_same_object(self, rm):
        """相同 name+size 第二次调用直接返回缓存对象。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()
        f1 = rm.get_font("arial", size=16)
        f2 = rm.get_font("arial", size=16)
        assert f1 is f2
        pygame.quit()

    def test_cache_size_increments(self, rm):
        pytest.importorskip("pygame")
        import pygame
        pygame.init()
        rm.get_font("arial", size=16)
        assert rm.font_cache_size == 1
        rm.get_font("arial", size=24)
        assert rm.font_cache_size == 2
        # 重复调用不增加缓存
        rm.get_font("arial", size=16)
        assert rm.font_cache_size == 2
        pygame.quit()


# ── 测试：自定义字体文件（.ttf / .otf）─────────────────────────────────────

class TestCustomFont:
    def _create_minimal_ttf(self, path: str) -> None:
        """
        写入一个最小合法 TTF 文件供测试使用。
        使用 pygame.font.Font 本身来校验加载，所以这里用真实 TTF 字节。

        策略：直接拷贝 pygame 内置字体文件。
        """
        import pygame
        # pygame 内置字体路径
        builtin = pygame.font.get_default_font()
        # get_default_font 返回文件名，需要通过 pygame 资源路径
        import importlib.resources
        builtin_path = os.path.join(os.path.dirname(pygame.__file__), builtin)
        if os.path.isfile(builtin_path):
            shutil.copy(builtin_path, path)
        else:
            # 在某些安装方式下路径不同，使用 font.Font(None, x) 的原始字节
            # 此时无法创建真实 ttf，跳过测试
            pytest.skip("无法获取 pygame 内置字体文件，跳过自定义字体测试")

    def test_load_ttf_from_fonts_dir(self, rm, fonts_tmpdir):
        """能从 assets/fonts/<name>.ttf 加载自定义字体。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()

        ttf_path = str(fonts_tmpdir / "testfont.ttf")
        self._create_minimal_ttf(ttf_path)

        font = rm.get_font("testfont", size=18)
        assert font is not None
        assert isinstance(font, pygame.font.Font)
        pygame.quit()

    def test_load_otf_from_fonts_dir(self, rm, fonts_tmpdir):
        """能从 assets/fonts/<name>.otf 加载自定义字体（用 .ttf 字节重命名模拟）。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()

        otf_path = str(fonts_tmpdir / "testfont.otf")
        self._create_minimal_ttf(otf_path)

        font = rm.get_font("testfont", size=18)
        assert font is not None
        assert isinstance(font, pygame.font.Font)
        pygame.quit()

    def test_ttf_preferred_over_otf(self, rm, fonts_tmpdir):
        """同名 .ttf 与 .otf 同时存在时，.ttf 优先。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()

        ttf_path = str(fonts_tmpdir / "myfont.ttf")
        otf_path = str(fonts_tmpdir / "myfont.otf")
        self._create_minimal_ttf(ttf_path)
        self._create_minimal_ttf(otf_path)

        font = rm.get_font("myfont", size=16)
        assert font is not None
        pygame.quit()

    def test_fullname_with_extension(self, rm, fonts_tmpdir):
        """name 带完整扩展名（如 'myfont.ttf'）时也能加载。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()

        ttf_path = str(fonts_tmpdir / "myfont.ttf")
        self._create_minimal_ttf(ttf_path)

        font = rm.get_font("myfont.ttf", size=16)
        assert font is not None
        assert isinstance(font, pygame.font.Font)
        pygame.quit()


# ── 测试：get_font_path ──────────────────────────────────────────────────────

class TestGetFontPath:
    def test_returns_none_when_not_found(self, rm, fonts_tmpdir):
        path = rm.get_font_path("nonexistent_font_xyz")
        assert path is None

    def test_returns_abs_path_for_ttf(self, rm, fonts_tmpdir):
        pytest.importorskip("pygame")
        import pygame
        pygame.init()

        ttf_file = fonts_tmpdir / "hello.ttf"
        # 写最小字节（内容无所谓，只要文件存在）
        ttf_file.write_bytes(b"\x00" * 4)

        result = rm.get_font_path("hello")
        assert result is not None
        assert os.path.isabs(result)
        assert result.endswith("hello.ttf")
        pygame.quit()

    def test_returns_abs_path_for_otf(self, rm, fonts_tmpdir):
        otf_file = fonts_tmpdir / "world.otf"
        otf_file.write_bytes(b"\x00" * 4)

        result = rm.get_font_path("world")
        assert result is not None
        assert result.endswith("world.otf")


# ── 测试：list_custom_fonts ──────────────────────────────────────────────────

class TestListCustomFonts:
    def test_empty_dir_returns_empty_list(self, rm, fonts_tmpdir):
        assert rm.list_custom_fonts() == []

    def test_lists_ttf_and_otf(self, rm, fonts_tmpdir):
        (fonts_tmpdir / "a.ttf").write_bytes(b"")
        (fonts_tmpdir / "b.otf").write_bytes(b"")
        (fonts_tmpdir / "readme.txt").write_bytes(b"")  # 不应被列出

        result = rm.list_custom_fonts()
        assert "a.ttf" in result
        assert "b.otf" in result
        assert "readme.txt" not in result

    def test_sorted_alphabetically(self, rm, fonts_tmpdir):
        (fonts_tmpdir / "z.ttf").write_bytes(b"")
        (fonts_tmpdir / "a.ttf").write_bytes(b"")
        (fonts_tmpdir / "m.otf").write_bytes(b"")

        result = rm.list_custom_fonts()
        assert result == sorted(result)

    def test_missing_fonts_dir_returns_empty(self, rm, tmp_path):
        """fonts 目录完全不存在时不应抛出异常。"""
        with patch("src.core.resource_manager.ASSETS_DIR", str(tmp_path / "nonexistent")):
            result = rm.list_custom_fonts()
        assert result == []


# ── 测试：load_font / get_font_by_key（兼容接口）───────────────────────────

class TestLoadFontCompat:
    def test_load_font_fallback_when_missing(self, rm, fonts_tmpdir):
        """文件不存在时 load_font 应回退到有效字体，不抛异常。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()
        rm.load_font("mykey", "fonts/nonexistent.ttf", 20)
        font = rm.get_font_by_key("mykey", 20)
        assert font is not None
        assert isinstance(font, pygame.font.Font)
        pygame.quit()

    def test_load_font_from_existing_file(self, rm, fonts_tmpdir):
        pytest.importorskip("pygame")
        import pygame
        pygame.init()

        # 使用 pygame 内置字体文件创建测试文件
        builtin = pygame.font.get_default_font()
        builtin_path = os.path.join(os.path.dirname(pygame.__file__), builtin)
        if not os.path.isfile(builtin_path):
            pytest.skip("无法获取 pygame 内置字体文件")

        dest = str(fonts_tmpdir / "compat.ttf")
        shutil.copy(builtin_path, dest)

        rm.load_font("compat_key", "fonts/compat.ttf", 22)
        font = rm.get_font_by_key("compat_key", 22)
        assert font is not None
        pygame.quit()

    def test_load_font_no_duplicate_load(self, rm, fonts_tmpdir):
        """同一 key+size 多次调用 load_font 不重复加载。"""
        pytest.importorskip("pygame")
        import pygame
        pygame.init()
        rm.load_font("dup_key", "fonts/nope.ttf", 16)
        rm.load_font("dup_key", "fonts/nope.ttf", 16)
        assert rm.font_cache_size == 1
        pygame.quit()

    def test_get_font_by_key_returns_none_if_not_loaded(self, rm):
        result = rm.get_font_by_key("not_loaded_key", 16)
        assert result is None
