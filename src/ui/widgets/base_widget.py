"""
UI 组件基类
对应文档 §6.1.1 界面层级，阶段2-1
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

if TYPE_CHECKING:
    pass


class UIComponent(ABC):
    """
    所有 UI 组件的基类。
    提供位置、大小、可见性、父子关系、事件响应和渲染接口。
    """

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        self._x: int = x
        self._y: int = y
        self._width: int = width
        self._height: int = height
        self._visible: bool = True
        self._enabled: bool = True
        self._children: List["UIComponent"] = []
        self._parent: Optional["UIComponent"] = None

    # ── 位置与大小 ────────────────────────────────────

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        dx = value - self._x
        self._x = value
        for child in self._children:
            child.x += dx

    @property
    def y(self) -> int:
        return self._y

    @y.setter
    def y(self, value: int) -> None:
        dy = value - self._y
        self._y = value
        for child in self._children:
            child.y += dy

    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        self._width = value

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        self._height = value

    def set_position(self, x: int, y: int) -> None:
        """同时设置位置，子组件跟随移动"""
        self.x = x
        self.y = y

    def set_size(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    @property
    def rect(self) -> "pygame.Rect":
        """返回当前组件的矩形区域（需要 pygame）"""
        if not _pygame_available:
            raise RuntimeError("pygame 未安装")
        return pygame.Rect(self._x, self._y, self._width, self._height)

    def get_bounds(self) -> Tuple[int, int, int, int]:
        """返回 (x, y, width, height)，不依赖 pygame"""
        return (self._x, self._y, self._width, self._height)

    # ── 可见性与启用状态 ──────────────────────────────

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    # ── 父子关系 ──────────────────────────────────────

    def add_child(self, child: "UIComponent") -> None:
        """添加子组件，子组件坐标相对父组件偏移"""
        child._parent = self
        self._children.append(child)

    def remove_child(self, child: "UIComponent") -> None:
        if child in self._children:
            child._parent = None
            self._children.remove(child)

    @property
    def children(self) -> List["UIComponent"]:
        return list(self._children)

    # ── 命中测试 ──────────────────────────────────────

    def contains_point(self, px: int, py: int) -> bool:
        """判断点 (px, py) 是否在组件范围内"""
        return (
            self._x <= px <= self._x + self._width
            and self._y <= py <= self._y + self._height
        )

    # ── 事件响应 ──────────────────────────────────────

    def handle_event(self, event) -> bool:
        """
        处理 pygame 事件。
        返回 True 表示事件已被消费，不再向下传递。
        默认将事件传递给所有子组件。
        """
        if not self._visible or not self._enabled:
            return False
        for child in reversed(self._children):  # 后添加的优先响应
            if child.handle_event(event):
                return True
        return False

    # ── 更新与渲染 ────────────────────────────────────

    def update(self, dt: float) -> None:
        """每帧逻辑更新，dt 单位为秒"""
        if not self._visible:
            return
        for child in self._children:
            child.update(dt)

    @abstractmethod
    def render(self, surface) -> None:
        """渲染组件到 surface，子类必须实现"""
        ...

    def _render_children(self, surface) -> None:
        """渲染所有可见子组件"""
        for child in self._children:
            if child.visible:
                child.render(surface)
