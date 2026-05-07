"""
地图导航场景 - 对应文档 §4.1
实现开发计划:
  4-3: 地图渲染 (节点连线、类型外观、BOSS 特殊显示)
  4-4: 地图导航逻辑 (当前位置、可移动高亮、已访问/未访问区分)
  4-5: 房间进入逻辑 (点击节点切换到对应场景)
"""
from __future__ import annotations

import logging
import math
import random
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.scenes.base_scene import BaseScene
from src.generation.map_generator import MapGenerator, MapNode, Floor
from src.generation.seed_manager import SeedManager
from src.ui.widgets.button import Button
from src.ui.widgets.label import Label
from src.ui.widgets.panel import Panel
from src.utils.constants import (
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_TEXT_PRIMARY,
    COLOR_WHITE, COLOR_DIVIDER, COLOR_TEXT_SECONDARY,
    COLOR_GOLD, COLOR_DANGER, COLOR_HEAL, COLOR_EPIC,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    SCREEN_WIDTH, SCREEN_HEIGHT,
)
from src.utils.enums import GameState, RoomType

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 常量: 节点渲染参数
# ═══════════════════════════════════════════════════════════════════════════════

# 节点圆形半径
_NODE_RADIUS = 18
_NODE_RADIUS_BOSS = 26
_NODE_RADIUS_ENTRY = 14

# 节点颜色方案 (bg_color, border_color, icon_char)
_NODE_STYLES: Dict[RoomType, Tuple[Tuple[int, int, int], Tuple[int, int, int], str]] = {
    RoomType.COMBAT: ((60, 60, 80), (120, 120, 140), "⚔"),
    RoomType.ELITE:  ((80, 40, 40), (200, 80, 80), "★"),
    RoomType.BOSS:   ((100, 20, 20), (255, 50, 50), "💀"),
    RoomType.SHOP:   ((40, 60, 40), (80, 180, 80), "$"),
    RoomType.EVENT:  ((50, 50, 80), (120, 120, 200), "?"),
    RoomType.REST:   ((30, 60, 60), (60, 180, 160), "♨"),
    RoomType.HIDDEN: ((40, 40, 40), (80, 80, 80), "…"),
}

# 连线颜色
_LINE_COLOR_NORMAL = (50, 55, 70)
_LINE_COLOR_AVAILABLE = (100, 180, 100)
_LINE_COLOR_VISITED = (80, 80, 100)

# 高亮/动画参数
_PULSE_SPEED = 3.0  # 呼吸动画速度
_HOVER_EXPAND = 4   # 悬停时半径增大

# 节点类型中文名
_ROOM_TYPE_NAMES: Dict[RoomType, str] = {
    RoomType.COMBAT: "战斗",
    RoomType.ELITE:  "精英",
    RoomType.BOSS:   "BOSS",
    RoomType.SHOP:   "商店",
    RoomType.EVENT:  "事件",
    RoomType.REST:   "休息",
    RoomType.HIDDEN: "隐藏",
}


# ═══════════════════════════════════════════════════════════════════════════════
# MapNavigationScene
# ═══════════════════════════════════════════════════════════════════════════════

class MapNavigationScene(BaseScene):
    """
    显示当前层的节点地图，玩家选择路径进入下一房间。

    功能:
    - 4-3: 渲染节点图 (不同类型不同颜色/图标, 连线, BOSS 特殊)
    - 4-4: 导航逻辑 (当前位置标记, 可移动节点高亮呼吸, 已访问灰化)
    - 4-5: 点击可用节点 → 移动玩家 → 根据节点类型切换对应场景
    """

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        # 楼层数据
        self._floor: Optional[Floor] = None
        self._floor_number: int = 1
        self._character_id: str = "knight"
        self._daily_mode: bool = False
        self._seed: int = 0

        # UI 组件
        self._widgets: list = []
        self._title_label: Optional[Label] = None
        self._info_label: Optional[Label] = None
        self._floor_label: Optional[Label] = None
        self._built: bool = False

        # 交互状态
        self._hovered_node: Optional[MapNode] = None
        self._pulse_time: float = 0.0  # 呼吸动画计时器

        # 字体缓存 (懒加载)
        self._font_icon: Optional[object] = None
        self._font_caption: Optional[object] = None

    # ══════════════════════════════════════════════════════════════════════
    # 场景生命周期
    # ══════════════════════════════════════════════════════════════════════

    def enter(self, **kwargs) -> None:
        """
        进入地图场景。
        kwargs:
            character_id: str  - 选择的角色 ID
            daily: bool        - 是否每日挑战模式
            floor_number: int  - 楼层编号 (默认 1)
            floor: Floor       - 已生成的楼层数据 (战斗结束后返回时传入)
        """
        self._character_id = kwargs.get("character_id", self._character_id)
        self._daily_mode = kwargs.get("daily", self._daily_mode)
        self._floor_number = kwargs.get("floor_number", self._floor_number)

        # 如果已有楼层数据 (从战斗/商店等返回)
        existing_floor = kwargs.get("floor", None)
        if existing_floor is not None:
            self._floor = existing_floor
        else:
            # 首次进入: 生成新楼层
            self._generate_floor()

        if not self._built:
            self._build_ui()
            self._built = True

        self._update_labels()
        self._hovered_node = None
        self._pulse_time = 0.0

        logger.info(
            "进入地图场景: 楼层=%d, 角色=%s, 每日=%s",
            self._floor_number, self._character_id, self._daily_mode
        )

    def exit(self) -> None:
        logger.info("离开地图场景")

    # ══════════════════════════════════════════════════════════════════════
    # 楼层生成
    # ══════════════════════════════════════════════════════════════════════

    def _generate_floor(self) -> None:
        """根据种子和楼层号生成地图"""
        # 确定种子
        if self._daily_mode:
            seed_mgr = SeedManager()
            self._seed = seed_mgr.daily_seed()
        else:
            if self._seed == 0:
                self._seed = random.randint(1, 999999999)

        # 组合种子: 基础种子 + 楼层号
        floor_seed = self._seed + self._floor_number * 1000
        rng = random.Random(floor_seed)

        # 加载楼层配置
        floor_config = self._load_floor_config(self._floor_number)

        # 生成
        gen = MapGenerator(rng)
        self._floor = gen.generate_floor(self._floor_number, floor_config)

        logger.info(
            "生成楼层 %d: %d 个节点, 种子=%d",
            self._floor_number, len(self._floor.nodes), floor_seed
        )

    def _load_floor_config(self, floor_number: int) -> dict:
        """加载楼层配置文件"""
        import os
        import yaml
        config_path = os.path.join("config", "levels", f"floor_{floor_number}.yaml")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return data.get("floor", {})
            except Exception as e:
                logger.warning("加载楼层配置失败: %s", e)

        # 默认配置
        return {
            "nodes_min": 8,
            "nodes_max": 12,
            "room_weights": {
                "combat": 50, "elite": 10,
                "shop": 15, "event": 15, "rest": 10
            }
        }

    # ══════════════════════════════════════════════════════════════════════
    # UI 构建
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """构建静态 UI 元素 (标题、信息栏、按钮)"""
        # 顶部楼层标题
        self._floor_label = Label(
            20, 12, 300, 30,
            text="",
            font_size=FONT_SIZE_H3,
            color=COLOR_TEXT_SECONDARY,
            align="left",
        )
        self._widgets.append(self._floor_label)

        # 顶部居中标题
        self._title_label = Label(
            SCREEN_WIDTH // 2 - 200, 10, 400, 36,
            text="地图",
            font_size=FONT_SIZE_H2,
            color=COLOR_TEXT_PRIMARY,
            align="center",
            bold=True,
        )
        self._widgets.append(self._title_label)

        # 底部信息栏
        self._info_label = Label(
            SCREEN_WIDTH // 2 - 300, SCREEN_HEIGHT - 40, 600, 28,
            text="选择一个节点前进",
            font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self._widgets.append(self._info_label)

        # 暂停按钮 (右上角)
        pause_btn = Button(
            SCREEN_WIDTH - 100, 12, 80, 32,
            text="暂停",
            font_size=FONT_SIZE_CAPTION,
            on_click=self._on_pause,
        )
        self._widgets.append(pause_btn)

    def _update_labels(self) -> None:
        """更新标签文本"""
        if self._floor_label:
            self._floor_label.text = f"第 {self._floor_number} 层"
        if self._title_label:
            title = "每日挑战" if self._daily_mode else "深渊地图"
            self._title_label.text = title

    # ══════════════════════════════════════════════════════════════════════
    # 字体懒加载
    # ══════════════════════════════════════════════════════════════════════

    def _get_icon_font(self):
        if self._font_icon is None and _pygame_available:
            self._font_icon = pygame.font.SysFont(
                "segoeuisymbol,microsoftyahei,simhei,arial", 16
            )
        return self._font_icon

    def _get_caption_font(self):
        if self._font_caption is None and _pygame_available:
            self._font_caption = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_CAPTION
            )
        return self._font_caption

    # ══════════════════════════════════════════════════════════════════════
    # 4-4: 事件处理 (导航逻辑)
    # ══════════════════════════════════════════════════════════════════════

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return

        # ESC → 暂停
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_pause()
            return

        # 鼠标移动 → 更新悬停状态
        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)

        # 鼠标点击 → 进入节点
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            clicked_node = self._get_node_at(event.pos)
            if clicked_node and clicked_node.available:
                self._enter_node(clicked_node)
                return

        # 传递给 UI 组件
        for widget in self._widgets:
            if widget.handle_event(event):
                break

    def _update_hover(self, mouse_pos: Tuple[int, int]) -> None:
        """更新鼠标悬停的节点"""
        node = self._get_node_at(mouse_pos)
        if node != self._hovered_node:
            self._hovered_node = node
            # 更新信息栏
            if node and self._info_label:
                type_name = _ROOM_TYPE_NAMES.get(node.room_type, "未知")
                if node.available:
                    self._info_label.text = f"点击进入: {type_name}"
                    self._info_label.color = COLOR_WHITE
                elif node.visited:
                    self._info_label.text = f"已通过: {type_name}"
                    self._info_label.color = COLOR_TEXT_SECONDARY
                elif node.is_current:
                    self._info_label.text = f"当前位置"
                    self._info_label.color = COLOR_GOLD
                else:
                    self._info_label.text = f"{type_name} (不可到达)"
                    self._info_label.color = COLOR_TEXT_SECONDARY
            elif self._info_label and node is None:
                self._info_label.text = "选择一个节点前进"
                self._info_label.color = COLOR_TEXT_SECONDARY

    def _get_node_at(self, pos: Tuple[int, int]) -> Optional[MapNode]:
        """检测鼠标位置是否在某个节点范围内"""
        if not self._floor:
            return None
        mx, my = pos
        for node in self._floor.nodes:
            radius = self._get_node_radius(node)
            dx = mx - node.x
            dy = my - node.y
            if dx * dx + dy * dy <= (radius + 4) ** 2:
                return node
        return None

    def _get_node_radius(self, node: MapNode) -> int:
        """根据节点类型获取渲染半径"""
        if node.room_type == RoomType.BOSS:
            return _NODE_RADIUS_BOSS
        if node.row == -1:  # 入口
            return _NODE_RADIUS_ENTRY
        return _NODE_RADIUS

    # ══════════════════════════════════════════════════════════════════════
    # 4-5: 房间进入逻辑
    # ══════════════════════════════════════════════════════════════════════

    def _enter_node(self, node: MapNode) -> None:
        """
        玩家移动到指定节点并根据类型切换场景。
        """
        if not self._floor:
            return

        logger.info("进入节点 %d (类型: %s)", node.node_id, node.room_type.value)

        # 更新楼层状态
        self._floor.mark_node_visited(node.node_id)

        # 根据节点类型切换场景
        target_state = self._room_type_to_state(node.room_type)
        if target_state is None:
            logger.warning("未知节点类型: %s, 跳过", node.room_type)
            return

        # 传递上下文给目标场景
        context = {
            "floor": self._floor,
            "floor_number": self._floor_number,
            "character_id": self._character_id,
            "daily": self._daily_mode,
            "seed": self._seed,
            "node_id": node.node_id,
            "room_type": node.room_type,
        }

        self.game.state_machine.change(target_state, **context)

    def _room_type_to_state(self, room_type: RoomType) -> Optional[GameState]:
        """将房间类型映射到游戏状态"""
        mapping = {
            RoomType.COMBAT: GameState.COMBAT,
            RoomType.ELITE:  GameState.COMBAT,
            RoomType.BOSS:   GameState.COMBAT,
            RoomType.SHOP:   GameState.SHOP,
            RoomType.EVENT:  GameState.EVENT,
            RoomType.REST:   GameState.REST,
        }
        return mapping.get(room_type)

    def _on_pause(self) -> None:
        """打开暂停菜单"""
        self.game.state_machine.change(
            GameState.PAUSE,
            return_state=GameState.MAP_NAVIGATION,
            floor=self._floor,
            floor_number=self._floor_number,
            character_id=self._character_id,
            daily=self._daily_mode,
            seed=self._seed,
        )

    # ══════════════════════════════════════════════════════════════════════
    # 更新
    # ══════════════════════════════════════════════════════════════════════

    def update(self, dt: float) -> None:
        """更新动画计时器和 UI 组件"""
        self._pulse_time += dt * _PULSE_SPEED
        for widget in self._widgets:
            widget.update(dt)

    # ══════════════════════════════════════════════════════════════════════
    # 4-3: 渲染
    # ══════════════════════════════════════════════════════════════════════

    def render(self, surface) -> None:
        if not _pygame_available:
            return

        # 1. 背景
        surface.fill(COLOR_BG_DARK)

        if self._floor:
            # 2. 绘制连线 (先画线, 节点覆盖在上面)
            self._render_connections(surface)

            # 3. 绘制节点
            self._render_nodes(surface)

            # 4. 绘制 tooltip (悬停信息)
            if self._hovered_node:
                self._render_tooltip(surface, self._hovered_node)

        # 5. UI 组件
        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)

    # ── 连线渲染 ──────────────────────────────────────────────────────────

    def _render_connections(self, surface) -> None:
        """绘制节点之间的有向连线"""
        if not self._floor:
            return

        for node in self._floor.nodes:
            for next_id in node.connections:
                next_node = self._floor.get_node_by_id(next_id)
                if next_node is None:
                    continue

                # 确定连线颜色
                if node.visited and next_node.available:
                    color = _LINE_COLOR_AVAILABLE
                    width = 2
                elif node.visited and next_node.visited:
                    color = _LINE_COLOR_VISITED
                    width = 2
                else:
                    color = _LINE_COLOR_NORMAL
                    width = 1

                start = (int(node.x), int(node.y))
                end = (int(next_node.x), int(next_node.y))

                # 绘制抗锯齿线
                pygame.draw.aaline(surface, color, start, end)
                # 再画一条普通线增加宽度感
                if width > 1:
                    pygame.draw.line(surface, color, start, end, width)

    # ── 节点渲染 ──────────────────────────────────────────────────────────

    def _render_nodes(self, surface) -> None:
        """绘制所有节点"""
        if not self._floor:
            return

        for node in self._floor.nodes:
            # 入口节点不单独渲染 (已被标记为 visited/current)
            if node.row == -1 and not node.is_current:
                self._render_entry_node(surface, node)
                continue

            self._render_single_node(surface, node)

    def _render_entry_node(self, surface, node: MapNode) -> None:
        """渲染入口节点 (小型标记)"""
        cx, cy = int(node.x), int(node.y)
        # 小三角形指示入口
        color = (100, 180, 100) if node.visited else (80, 80, 100)
        points = [
            (cx, cy - 10),
            (cx - 8, cy + 6),
            (cx + 8, cy + 6),
        ]
        pygame.draw.polygon(surface, color, points)

    def _render_single_node(self, surface, node: MapNode) -> None:
        """渲染单个节点"""
        cx, cy = int(node.x), int(node.y)
        base_radius = self._get_node_radius(node)

        # 获取样式
        style = _NODE_STYLES.get(
            node.room_type,
            ((50, 50, 50), (100, 100, 100), "?")
        )
        bg_color, border_color, icon_char = style

        # ── 状态修饰 ──
        radius = base_radius
        alpha_factor = 1.0

        if node.is_current:
            # 当前节点: 金色光环 + 脉冲
            pulse = 0.5 + 0.5 * math.sin(self._pulse_time * 1.5)
            glow_radius = radius + 6 + int(pulse * 4)
            glow_color = (255, 215, 0)
            pygame.draw.circle(surface, glow_color, (cx, cy), glow_radius, 2)

        elif node.available:
            # 可移动节点: 绿色呼吸高亮
            pulse = 0.5 + 0.5 * math.sin(self._pulse_time)
            glow_radius = radius + 3 + int(pulse * 3)
            glow_color = (80, 200, 80)
            pygame.draw.circle(surface, glow_color, (cx, cy), glow_radius, 2)

        elif node.visited:
            # 已访问: 略微灰化
            alpha_factor = 0.6
            bg_color = self._dim_color(bg_color, 0.5)
            border_color = self._dim_color(border_color, 0.5)

        else:
            # 未访问且不可达: 暗色
            alpha_factor = 0.4
            bg_color = self._dim_color(bg_color, 0.3)
            border_color = self._dim_color(border_color, 0.3)

        # 悬停放大效果
        if node == self._hovered_node and (node.available or node.is_current):
            radius += _HOVER_EXPAND

        # ── 绘制节点圆形 ──
        # BOSS 特殊: 八边形
        if node.room_type == RoomType.BOSS:
            self._draw_octagon(surface, cx, cy, radius, bg_color, border_color)
        else:
            pygame.draw.circle(surface, bg_color, (cx, cy), radius)
            pygame.draw.circle(surface, border_color, (cx, cy), radius, 2)

        # ── 绘制图标文字 ──
        font = self._get_icon_font()
        if font:
            icon_color = COLOR_WHITE if alpha_factor > 0.5 else (150, 150, 150)
            icon_surf = font.render(icon_char, True, icon_color)
            icon_rect = icon_surf.get_rect(center=(cx, cy))
            surface.blit(icon_surf, icon_rect)

    def _draw_octagon(self, surface, cx: int, cy: int, radius: int,
                      bg_color: Tuple[int, int, int],
                      border_color: Tuple[int, int, int]) -> None:
        """绘制八边形 (用于 BOSS 节点)"""
        points = []
        for i in range(8):
            angle = math.pi / 8 + i * math.pi / 4
            px = cx + int(radius * math.cos(angle))
            py = cy + int(radius * math.sin(angle))
            points.append((px, py))
        pygame.draw.polygon(surface, bg_color, points)
        pygame.draw.polygon(surface, border_color, points, 2)

    # ── Tooltip 渲染 ─────────────────────────────────────────────────────

    def _render_tooltip(self, surface, node: MapNode) -> None:
        """在悬停节点旁边绘制简易 tooltip"""
        font = self._get_caption_font()
        if not font:
            return

        type_name = _ROOM_TYPE_NAMES.get(node.room_type, "未知")
        if node.available:
            tip_text = f"{type_name} - 点击进入"
        elif node.is_current:
            tip_text = f"当前位置"
        elif node.visited:
            tip_text = f"{type_name} (已完成)"
        else:
            tip_text = f"{type_name}"

        text_surf = font.render(tip_text, True, COLOR_WHITE)
        tw, th = text_surf.get_size()

        # tooltip 位置 (节点上方)
        tx = int(node.x) - tw // 2
        ty = int(node.y) - self._get_node_radius(node) - th - 10

        # 确保不超出屏幕
        tx = max(4, min(tx, SCREEN_WIDTH - tw - 4))
        ty = max(4, ty)

        # 背景
        padding = 4
        bg_rect = pygame.Rect(
            tx - padding, ty - padding,
            tw + padding * 2, th + padding * 2
        )
        bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg_surf.fill((20, 20, 30, 200))
        surface.blit(bg_surf, bg_rect.topleft)
        pygame.draw.rect(surface, COLOR_DIVIDER, bg_rect, 1)

        # 文字
        surface.blit(text_surf, (tx, ty))

    # ── 辅助方法 ─────────────────────────────────────────────────────────

    @staticmethod
    def _dim_color(color: Tuple[int, int, int],
                   factor: float) -> Tuple[int, int, int]:
        """将颜色按比例变暗"""
        return (
            int(color[0] * factor),
            int(color[1] * factor),
            int(color[2] * factor),
        )
