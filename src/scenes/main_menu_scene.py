"""
主菜单场景
对应文档 §6.1，阶段2-7（UI）/ 阶段2-8（交互）
"""
from __future__ import annotations
import logging
import random
import math
from typing import TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.scenes.base_scene import BaseScene
from src.ui.widgets.button import Button
from src.ui.widgets.label import Label
from src.ui.widgets.panel import Panel
from src.ui.widgets.dialog import Dialog
from src.utils.constants import (
    COLOR_BG_DARK, COLOR_TEXT_PRIMARY,
    COLOR_WHITE, COLOR_GOLD,
    FONT_SIZE_H3, FONT_SIZE_BODY,
    SCREEN_WIDTH, SCREEN_HEIGHT,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)

# ── 布局常量 ──────────────────────────────────────────────────
_BTN_W   = 300
_BTN_H   = 48
_BTN_GAP = 10
_CENTER_X = SCREEN_WIDTH // 2
_PANEL_W  = 460
_PANEL_H  = 590
_PANEL_X  = _CENTER_X - _PANEL_W // 2
_PANEL_Y  = 40
_TITLE_Y  = _PANEL_Y + 24

# 按钮颜色方案
_BTN_NORMAL_BG      = (25, 38, 72)
_BTN_HOVER_BG       = (42, 68, 115)
_BTN_PRESSED_BG     = (18, 28, 52)
_BTN_BORDER         = (35, 52, 85)
_BTN_PRIMARY_BG     = (233, 69, 96)
_BTN_PRIMARY_HOVER  = (252, 88, 114)
_BTN_PRIMARY_PRESS  = (195, 50, 75)
_BTN_PRIMARY_BORDER = (255, 105, 130)
_BTN_QUIT_BG        = (28, 28, 42)
_BTN_QUIT_HOVER     = (50, 50, 70)
_BTN_QUIT_BORDER    = (48, 48, 65)

# 科技感背景色系
_SCI_FI_CYAN        = (0, 210, 230)
_SCI_FI_CYAN_DIM    = (0, 140, 160)
_SCI_FI_CYAN_FAINT  = (0, 60, 80)
_SCI_FI_GRID        = (0, 35, 55)
_SCI_FI_NODE        = (0, 200, 220)
_SCI_FI_LINK_DIM    = (0, 45, 65)

_PARTICLE_COUNT = 55


class Particle:
    """科技感漂浮粒子"""
    __slots__ = ('x', 'y', 'vx', 'vy', 'size', 'alpha', 'max_alpha', 'fade_dir')

    def __init__(self):
        self.x = float(random.randint(0, SCREEN_WIDTH))
        self.y = float(random.randint(0, SCREEN_HEIGHT))
        self.vx = random.uniform(-0.2, 0.2)
        self.vy = random.uniform(-0.5, -0.15)
        self.size = random.randint(1, 2)
        self.alpha = float(random.randint(20, 90))
        self.max_alpha = self.alpha
        self.fade_dir = random.choice([-1, 1])

    def update(self, dt: float) -> None:
        speed = dt * 60
        self.x += self.vx * speed
        self.y += self.vy * speed
        self.alpha += self.fade_dir * 0.5 * speed
        if self.alpha >= self.max_alpha:
            self.fade_dir = -1
        elif self.alpha <= 10:
            self.fade_dir = 1
        if self.x < -10:
            self.x = float(SCREEN_WIDTH + 10)
        elif self.x > SCREEN_WIDTH + 10:
            self.x = -10
        if self.y < -10:
            self.y = float(SCREEN_HEIGHT + 10)
        elif self.y > SCREEN_HEIGHT + 10:
            self.y = -10


class MainMenuScene(BaseScene):
    """主菜单场景 - 科技感 UI"""

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._exit_dialog: Dialog | None = None
        self._bg_surface = None
        self._built = False
        self._continue_btn: Button | None = None
        self._shards_label: Label | None = None
        self._particles: list[Particle] = []
        self._time = 0.0
        self._scanline_offset = 0.0

    # ── 场景生命周期 ────────────────────────────────────

    def enter(self, **kwargs) -> None:
        if not self._built:
            self._build_ui()
            self._built = True
        self._refresh_dynamic()
        if self._bg_surface is None:
            self._bg_surface = self._generate_sci_fi_background()
        if not self._particles:
            self._particles = [Particle() for _ in range(_PARTICLE_COUNT)]
        logger.info("进入主菜单")

    def exit(self) -> None:
        logger.info("离开主菜单")

    # ── 科技感背景生成 ─────────────────────────────────

    def _generate_sci_fi_background(self):
        """生成科技感背景 Surface（缓存复用）"""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        W, H = SCREEN_WIDTH, SCREEN_HEIGHT

        # ── 1. 深色渐变底 ──────────────────────────────
        num_bands = 80
        band_h = H // num_bands
        for i in range(num_bands):
            t = i / num_bands
            r = int(5 + t * 10)
            g = int(6 + t * 8)
            b = int(15 + t * 25)
            rect = pygame.Rect(0, i * band_h, W, band_h + 1)
            surf.fill((r, g, b), rect)

        # ── 2. 大型六边形网格 ──────────────────────────
        hex_w = 120
        hex_h = int(hex_w * math.sqrt(3) / 2)
        cols = W // hex_w + 2
        rows = H // hex_h + 2
        for row in range(rows):
            offset_x = (hex_w // 2) if row % 2 else 0
            for col in range(cols):
                cx = col * hex_w + offset_x - hex_w
                cy = row * hex_h - hex_h
                pts = []
                for j in range(6):
                    angle = math.pi / 180 * (60 * j - 30)
                    px = cx + hex_w * 0.42 * math.cos(angle)
                    py = cy + hex_w * 0.42 * math.sin(angle)
                    pts.append((int(px), int(py)))
                if any(0 <= p[0] <= W and 0 <= p[1] <= H for p in pts):
                    pygame.draw.polygon(surf, _SCI_FI_GRID, pts, 1)

        # ── 3. 水平扫描线 ──────────────────────────────
        for y in range(0, H, 4):
            alpha = random.randint(3, 12)
            color = (0, 180, 200, alpha)
            s = pygame.Surface((W, 1), pygame.SRCALPHA)
            s.fill(color)
            surf.blit(s, (0, y))

        # ── 4. 对角线数据流 ────────────────────────────
        for i in range(6):
            start_x = random.randint(-200, W + 200)
            start_y = random.randint(-100, 50)
            length = random.randint(300, 800)
            end_x = start_x + length
            end_y = start_y + int(length * 0.55)
            alpha = random.randint(15, 40)
            color = (0, 180, 210, alpha)
            for _w in range(random.randint(1, 3)):
                s = pygame.Surface((W, H), pygame.SRCALPHA)
                pygame.draw.line(
                    s, color,
                    (start_x + _w * 30, start_y),
                    (end_x + _w * 30, end_y),
                    random.randint(1, 2),
                )
                surf.blit(s, (0, 0))

        # ── 5. 科技感节点与连线 ────────────────────────
        nodes = []
        for _ in range(10):
            nx = random.randint(60, W - 60)
            ny = random.randint(40, H - 40)
            nodes.append((nx, ny))
        # 连线
        for i, (ax, ay) in enumerate(nodes):
            for bx, by in nodes[i + 1:]:
                dist = math.hypot(bx - ax, by - ay)
                if dist < 350:
                    alpha = int(max(5, 40 * (1 - dist / 350)))
                    s = pygame.Surface((W, H), pygame.SRCALPHA)
                    pygame.draw.line(s, (0, 180, 210, alpha), (ax, ay), (bx, by), 1)
                    surf.blit(s, (0, 0))
        # 节点
        for nx, ny in nodes:
            s = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(s, (0, 220, 240, 80), (5, 5), 3)
            pygame.draw.circle(s, (255, 255, 255, 200), (5, 5), 1)
            surf.blit(s, (nx - 5, ny - 5))

        # ── 6. 四角科技框架 ────────────────────────────
        corner_mar = 20
        corner_len = 60
        corners = [
            (corner_mar, corner_mar, 1, 1),
            (W - corner_mar, corner_mar, -1, 1),
            (corner_mar, H - corner_mar, 1, -1),
            (W - corner_mar, H - corner_mar, -1, -1),
        ]
        for cx, cy, dx, dy in corners:
            ix = 1 if dx > 0 else -1
            iy = 1 if dy > 0 else -1
            # 外框 L 形
            pts_outer = [
                (cx + ix * corner_len, cy),
                (cx, cy),
                (cx, cy + iy * corner_len),
            ]
            pygame.draw.lines(surf, _SCI_FI_CYAN_DIM, False, pts_outer, 1)
            # 内框短线
            pts_inner = [
                (cx + ix * (corner_len // 3), cy),
                (cx, cy),
                (cx, cy + iy * (corner_len // 3)),
            ]
            pygame.draw.lines(surf, _SCI_FI_CYAN, False, pts_inner, 1)
            # 角落小菱形
            pygame.draw.circle(surf, _SCI_FI_CYAN, (cx, cy), 3, 1)

        # ── 7. 中心能量环 ──────────────────────────────
        cx, cy = _CENTER_X, SCREEN_HEIGHT // 2 + 20
        ring_surf = pygame.Surface((500, 500), pygame.SRCALPHA)
        for r in range(230, 0, -3):
            a = max(0, int(3 * (1 - r / 230)))
            pygame.draw.circle(ring_surf, (0, 180, 210, a), (250, 250), r, 1)
        surf.blit(ring_surf, (cx - 250, cy - 250))

        return surf

    # ── UI 构建 ────────────────────────────────────────

    def _build_ui(self) -> None:
        """构建主菜单所有 UI 元素"""

        # ── 中央菜单面板（半透明） ─────────────────────
        menu_panel = Panel(
            _PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H,
            bg_color=(10, 18, 40),
            bg_alpha=225,
            border_color=(0, 160, 185),
            border_width=1,
            border_radius=14,
        )
        self._widgets.append(menu_panel)

        # ── 面板顶部装饰线 ─────────────────────────────
        panel_accent = Panel(
            _PANEL_X + 24, _PANEL_Y + 1, _PANEL_W - 48, 1,
            bg_color=_SCI_FI_CYAN_DIM,
            bg_alpha=80,
            border_color=None,
            border_width=0,
        )
        self._widgets.append(panel_accent)

        # ── 标题 ──────────────────────────────────────
        title = Label(
            _CENTER_X - 230, _TITLE_Y, 460, 70,
            text="深渊回响：无尽轮回",
            font_size=42,
            color=COLOR_TEXT_PRIMARY,
            align="center",
            bold=True,
        )
        subtitle = Label(
            _CENTER_X - 220, _TITLE_Y + 68, 440, 26,
            text="ECHOES OF THE ABYSS",
            font_size=14,
            color=(100, 195, 210),
            align="center",
        )
        self._widgets.extend([title, subtitle])

        # ── 标题下方装饰分隔线 ─────────────────────────
        div_y = _TITLE_Y + 102
        left_orn = Panel(
            _CENTER_X - 140, div_y, 5, 5,
            bg_color=_SCI_FI_CYAN_DIM,
            border_color=None,
            border_width=0,
            border_radius=2,
        )
        right_orn = Panel(
            _CENTER_X + 135, div_y, 5, 5,
            bg_color=_SCI_FI_CYAN_DIM,
            border_color=None,
            border_width=0,
            border_radius=2,
        )
        div_line = Panel(
            _CENTER_X - 115, div_y + 2, 230, 1,
            bg_color=(0, 60, 80),
            border_color=None,
            border_width=0,
        )
        self._widgets.extend([left_orn, right_orn, div_line])

        # ── 按钮列表 ──────────────────────────────────
        btn_start_y = _TITLE_Y + 128
        buttons_config = [
            ("继续游戏",   self._on_continue,        "primary"),
            ("开始游戏",   self._on_start_game,       "normal"),
            ("每日挑战",   self._on_daily_challenge,   "normal"),
            ("灵魂祭坛",   self._on_meta_upgrade,      "normal"),
            ("图鉴",       self._on_codex,             "normal"),
            ("设置",       self._on_settings,          "normal"),
            ("退出游戏",   self._on_quit,              "quit"),
        ]

        for i, (text, cb, style) in enumerate(buttons_config):
            btn_y = btn_start_y + i * (_BTN_H + _BTN_GAP)
            btn_x = _CENTER_X - _BTN_W // 2

            if style == "primary":
                btn = Button(
                    btn_x, btn_y, _BTN_W, _BTN_H,
                    text=text,
                    font_size=FONT_SIZE_H3,
                    on_click=cb,
                    normal_bg=_BTN_PRIMARY_BG,
                    hover_bg=_BTN_PRIMARY_HOVER,
                    pressed_bg=_BTN_PRIMARY_PRESS,
                    border_color=_BTN_PRIMARY_BORDER,
                    text_color=COLOR_WHITE,
                    border_radius=8,
                )
                self._continue_btn = btn
            elif style == "quit":
                btn = Button(
                    btn_x, btn_y, _BTN_W, _BTN_H,
                    text=text,
                    font_size=FONT_SIZE_BODY,
                    on_click=cb,
                    normal_bg=_BTN_QUIT_BG,
                    hover_bg=_BTN_QUIT_HOVER,
                    pressed_bg=(20, 20, 30),
                    border_color=_BTN_QUIT_BORDER,
                    text_color=(150, 150, 170),
                    border_radius=8,
                )
            else:
                btn = Button(
                    btn_x, btn_y, _BTN_W, _BTN_H,
                    text=text,
                    font_size=FONT_SIZE_BODY,
                    on_click=cb,
                    normal_bg=_BTN_NORMAL_BG,
                    hover_bg=_BTN_HOVER_BG,
                    pressed_bg=_BTN_PRESSED_BG,
                    border_color=_BTN_BORDER,
                    text_color=COLOR_WHITE,
                    border_radius=8,
                )
            self._widgets.append(btn)

        # ── "退出游戏"上方分隔线 ───────────────────────
        sep_y = btn_start_y + 6 * (_BTN_H + _BTN_GAP) - _BTN_GAP // 2
        sep = Panel(
            _CENTER_X - 120, sep_y, 240, 1,
            bg_color=(0, 50, 70),
            border_color=None,
            border_width=0,
        )
        self._widgets.append(sep)

        # ── 版本号 ────────────────────────────────────
        version_label = Label(
            SCREEN_WIDTH - 165, SCREEN_HEIGHT - 32,
            155, 24,
            text="v0.3.0-alpha",
            font_size=13,
            color=(55, 60, 80),
            align="right",
        )
        self._widgets.append(version_label)

        # ── 灵魂碎片（左下角） ──────────────────────────
        self._shards_label = Label(
            28, SCREEN_HEIGHT - 36, 350, 28,
            text="◇ 灵魂碎片：0",
            font_size=15,
            color=COLOR_GOLD,
            align="left",
            bold=True,
        )
        self._widgets.append(self._shards_label)

        # ── 退出确认对话框 ────────────────────────────
        self._exit_dialog = Dialog(
            title="退出游戏",
            content="确定要退出游戏吗？",
            confirm_text="确定退出",
            cancel_text="取消",
            on_confirm=self._do_quit,
            on_cancel=None,
            close_on_overlay=True,
        )

    # ── 动态刷新 ──────────────────────────────────────

    def _refresh_dynamic(self) -> None:
        """每次进入主菜单时刷新动态状态：是否能继续、灵魂碎片数"""
        if self._continue_btn is not None:
            try:
                has_save = self.game.save_manager.has_run_state()
            except Exception:
                has_save = False
            self._continue_btn.enabled = has_save
        if self._shards_label is not None:
            try:
                meta = self.game.save_manager.load_meta_progress()
                self._shards_label.text = f"◇ 灵魂碎片：{meta.soul_shards}"
            except Exception:
                pass

    # ── 按钮回调 ──────────────────────────────────────

    def _on_continue(self) -> None:
        sm = getattr(self.game, "save_manager", None)
        if sm is None or not sm.has_run_state():
            logger.info("点击：继续游戏（没有可用存档）")
            return
        run_model = sm.load_run_state()
        if run_model is None:
            return
        self.game.run_state.restore_from_run_state_model(run_model)
        logger.info(
            "继续上一局：char=%s floor=%d",
            self.game.run_state.character_id,
            self.game.run_state.current_floor,
        )
        self.game.state_machine.change(
            GameState.MAP_NAVIGATION,
            character_id=self.game.run_state.character_id,
            daily=self.game.run_state.daily,
            floor_number=self.game.run_state.current_floor,
        )

    def _on_start_game(self) -> None:
        logger.info("点击：开始游戏")
        try:
            self.game.save_manager.delete_run_state()
        except Exception:
            pass
        self.game.state_machine.change(GameState.CHARACTER_SELECT)

    def _on_daily_challenge(self) -> None:
        logger.info("点击：每日挑战")
        try:
            self.game.save_manager.delete_run_state()
        except Exception:
            pass
        self.game.state_machine.change(GameState.CHARACTER_SELECT, daily=True)

    def _on_meta_upgrade(self) -> None:
        logger.info("点击：灵魂祭坛 / 局外强化")
        self.game.state_machine.change(GameState.META_UPGRADE)

    def _on_codex(self) -> None:
        logger.info("点击：图鉴")
        self.game.state_machine.change(GameState.CODEX)

    def _on_settings(self) -> None:
        logger.info("点击：设置")
        self.game.state_machine.change(GameState.SETTINGS)

    def _on_quit(self) -> None:
        if self._exit_dialog:
            self._exit_dialog.show()

    def _do_quit(self) -> None:
        logger.info("用户确认退出游戏")
        self.game.running = False

    # ── 事件 / 更新 / 渲染 ────────────────────────────

    def handle_event(self, event) -> None:
        if self._exit_dialog and self._exit_dialog.visible:
            self._exit_dialog.handle_event(event)
            return
        for widget in self._widgets:
            if widget.handle_event(event):
                break

    def update(self, dt: float) -> None:
        self._time += dt
        self._scanline_offset = (self._scanline_offset + dt * 30) % 4
        for p in self._particles:
            p.update(dt)
        for widget in self._widgets:
            widget.update(dt)

    def render(self, surface) -> None:
        if not _pygame_available:
            return

        # ── 科技感静态背景 ────────────────────────────
        if self._bg_surface:
            surface.blit(self._bg_surface, (0, 0))
        else:
            surface.fill(COLOR_BG_DARK)

        # ── 扫描线动画叠加 ────────────────────────────
        self._draw_scanlines(surface)

        # ── 粒子 ──────────────────────────────────────
        for p in self._particles:
            a = max(0, min(255, int(p.alpha)))
            color = (0, 220, 240, a) if p.size == 1 else (100, 160, 210, a)
            try:
                ps = pygame.Surface((p.size * 2 + 2, p.size * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(ps, color, (p.size + 1, p.size + 1), p.size)
                surface.blit(ps, (int(p.x), int(p.y)))
            except Exception:
                pass

        # ── 标题光晕（在 widget 之前渲染） ─────────────
        self._draw_title_glow(surface)

        # ── Widgets ───────────────────────────────────
        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)

        # ── 对话框最后渲染 ────────────────────────────
        if self._exit_dialog:
            self._exit_dialog.render(surface)

    # ── 装饰绘制辅助方法 ──────────────────────────────

    def _draw_scanlines(self, surface) -> None:
        """移动扫描线效果"""
        try:
            offset = int(self._scanline_offset) % 4
            s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for y in range(offset, SCREEN_HEIGHT, 4):
                s.fill((0, 180, 210, 5), pygame.Rect(0, y, SCREEN_WIDTH, 1))
            surface.blit(s, (0, 0))
        except Exception:
            pass

    def _draw_title_glow(self, surface) -> None:
        """在主标题位置绘制光晕"""
        try:
            font = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", 42, bold=True
            )
            text = "深渊回响：无尽轮回"
            text_surf = font.render(text, True, COLOR_TEXT_PRIMARY)
            text_rect = text_surf.get_rect(center=(_CENTER_X, _TITLE_Y + 32))

            glow_pass = [
                ((233, 69, 96), 35, 3),
                ((233, 69, 96), 20, 2),
                ((233, 69, 96), 10, 1),
            ]
            for color, alpha, offset in glow_pass:
                gs = font.render(text, True, color)
                gs.set_alpha(alpha)
                for ox, oy in [
                    (-offset, 0), (offset, 0), (0, -offset), (0, offset),
                    (-offset, -offset), (offset, -offset), (-offset, offset), (offset, offset),
                ]:
                    surface.blit(
                        gs, (text_rect.x + ox, text_rect.y + oy - 2)
                    )
        except Exception:
            pass
