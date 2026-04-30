"""
设置场景
对应文档 §6.1，阶段2-9
"""
from __future__ import annotations
import json
import os
import logging
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
from src.ui.widgets.slider import Slider
from src.utils.constants import (
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_TEXT_PRIMARY,
    COLOR_WHITE, COLOR_DIVIDER, COLOR_TEXT_SECONDARY,
    FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY,
    SCREEN_WIDTH, SCREEN_HEIGHT, SAVE_DIR,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)

_SETTINGS_FILE = os.path.join(SAVE_DIR, "settings.json")

# 支持的分辨率列表
_RESOLUTIONS = [
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
]

_DEFAULT_SETTINGS = {
    "music_volume":  0.7,
    "sound_volume":  0.8,
    "resolution_idx": 0,    # 索引到 _RESOLUTIONS
    "fullscreen":    False,
}


class SettingsScene(BaseScene):
    """
    设置场景：
    - 音乐音量 / 音效音量（滑块）
    - 分辨率选择（← → 切换）
    - 全屏/窗口模式切换
    - 保存 / 返回按钮
    """

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._settings = dict(_DEFAULT_SETTINGS)
        self._built = False
        # 动态更新的标签引用
        self._resolution_label: Label | None = None
        self._fullscreen_btn:   Button | None = None

    # ── 场景生命周期 ──────────────────────────────────

    def enter(self, **kwargs) -> None:
        self._load_settings()
        if not self._built:
            self._build_ui()
            self._built = True
        else:
            # 重进时刷新显示
            self._refresh_ui()
        logger.info("进入设置场景")

    def exit(self) -> None:
        logger.info("离开设置场景")

    # ── 设置读写 ──────────────────────────────────────

    def _load_settings(self) -> None:
        """从 saves/settings.json 加载设置"""
        try:
            if os.path.exists(_SETTINGS_FILE):
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._settings.update(data)
        except Exception as e:
            logger.warning(f"加载设置失败: {e}，使用默认值")

    def _save_settings(self) -> None:
        """将当前设置写入 saves/settings.json"""
        os.makedirs(SAVE_DIR, exist_ok=True)
        try:
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            logger.info("设置已保存")
        except Exception as e:
            logger.error(f"保存设置失败: {e}")

    # ── UI 构建 ────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── 背景 ──────────────────────────────────────
        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK, border_color=None, border_width=0,
        )
        self._widgets.append(bg)

        # ── 中央面板 ──────────────────────────────────
        panel_w, panel_h = 580, 440
        panel_x = (SCREEN_WIDTH  - panel_w) // 2
        panel_y = (SCREEN_HEIGHT - panel_h) // 2
        card = Panel(
            panel_x, panel_y, panel_w, panel_h,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_DIVIDER,
            border_width=2,
            border_radius=8,
        )
        self._widgets.append(card)

        # ── 标题 ──────────────────────────────────────
        title = Label(
            panel_x, panel_y + 20,
            panel_w, 40,
            text="设置", font_size=FONT_SIZE_H2,
            color=COLOR_TEXT_PRIMARY, align="center", bold=True,
        )
        self._widgets.append(title)

        # 分割线
        div = Panel(
            panel_x + 24, panel_y + 68,
            panel_w - 48, 1,
            bg_color=COLOR_DIVIDER, border_color=None, border_width=0,
        )
        self._widgets.append(div)

        row_y = panel_y + 88
        lbl_w, ctrl_x = 200, panel_x + 240
        ctrl_w = panel_w - 240 - 24

        # ── 音乐音量 ──────────────────────────────────
        self._widgets.append(Label(
            panel_x + 24, row_y, lbl_w, 36,
            text="音乐音量", font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE, align="left",
        ))
        music_slider = Slider(
            ctrl_x, row_y + 4, ctrl_w, 28,
            min_val=0.0, max_val=1.0,
            value=self._settings["music_volume"],
            on_change=self._on_music_volume,
        )
        self._widgets.append(music_slider)

        row_y += 54

        # ── 音效音量 ──────────────────────────────────
        self._widgets.append(Label(
            panel_x + 24, row_y, lbl_w, 36,
            text="音效音量", font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE, align="left",
        ))
        sound_slider = Slider(
            ctrl_x, row_y + 4, ctrl_w, 28,
            min_val=0.0, max_val=1.0,
            value=self._settings["sound_volume"],
            on_change=self._on_sound_volume,
        )
        self._widgets.append(sound_slider)

        row_y += 54

        # ── 分辨率 ────────────────────────────────────
        self._widgets.append(Label(
            panel_x + 24, row_y, lbl_w, 36,
            text="分辨率", font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE, align="left",
        ))
        # 左箭头
        btn_prev = Button(
            ctrl_x, row_y + 2, 36, 32,
            text="<", on_click=self._on_res_prev,
        )
        self._widgets.append(btn_prev)
        # 分辨率显示标签
        res = _RESOLUTIONS[self._settings["resolution_idx"]]
        self._resolution_label = Label(
            ctrl_x + 40, row_y, ctrl_w - 80, 36,
            text=f"{res[0]}×{res[1]}",
            font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE, align="center",
        )
        self._widgets.append(self._resolution_label)
        # 右箭头
        btn_next = Button(
            ctrl_x + ctrl_w - 36, row_y + 2, 36, 32,
            text=">", on_click=self._on_res_next,
        )
        self._widgets.append(btn_next)

        row_y += 54

        # ── 全屏模式 ──────────────────────────────────
        self._widgets.append(Label(
            panel_x + 24, row_y, lbl_w, 36,
            text="全屏模式", font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE, align="left",
        ))
        fs_text = "开启" if self._settings["fullscreen"] else "关闭"
        self._fullscreen_btn = Button(
            ctrl_x, row_y + 2, 120, 32,
            text=fs_text, on_click=self._on_toggle_fullscreen,
        )
        self._widgets.append(self._fullscreen_btn)

        row_y += 54

        # ── 底部按钮 ──────────────────────────────────
        btn_y = panel_y + panel_h - 60
        btn_w = (panel_w - 72) // 2

        save_btn = Button(
            panel_x + 24, btn_y, btn_w, 44,
            text="保存设置",
            on_click=self._on_save,
            normal_bg=(30, 70, 30),
            hover_bg=(50, 110, 50),
            border_color=(60, 180, 60),
        )
        back_btn = Button(
            panel_x + 24 + btn_w + 24, btn_y, btn_w, 44,
            text="返回主菜单",
            on_click=self._on_back,
        )
        self._widgets.extend([save_btn, back_btn])

    def _refresh_ui(self) -> None:
        """重入场景时刷新动态控件"""
        if self._resolution_label:
            res = _RESOLUTIONS[self._settings["resolution_idx"]]
            self._resolution_label.text = f"{res[0]}×{res[1]}"
        if self._fullscreen_btn:
            self._fullscreen_btn.text = "开启" if self._settings["fullscreen"] else "关闭"

    # ── 控件回调 ──────────────────────────────────────

    def _on_music_volume(self, value: float) -> None:
        self._settings["music_volume"] = round(value, 2)
        if _pygame_available:
            try:
                pygame.mixer.music.set_volume(value)
            except Exception:
                pass

    def _on_sound_volume(self, value: float) -> None:
        self._settings["sound_volume"] = round(value, 2)

    def _on_res_prev(self) -> None:
        idx = self._settings["resolution_idx"]
        idx = (idx - 1) % len(_RESOLUTIONS)
        self._settings["resolution_idx"] = idx
        if self._resolution_label:
            res = _RESOLUTIONS[idx]
            self._resolution_label.text = f"{res[0]}×{res[1]}"

    def _on_res_next(self) -> None:
        idx = self._settings["resolution_idx"]
        idx = (idx + 1) % len(_RESOLUTIONS)
        self._settings["resolution_idx"] = idx
        if self._resolution_label:
            res = _RESOLUTIONS[idx]
            self._resolution_label.text = f"{res[0]}×{res[1]}"

    def _on_toggle_fullscreen(self) -> None:
        self._settings["fullscreen"] = not self._settings["fullscreen"]
        if self._fullscreen_btn:
            self._fullscreen_btn.text = "开启" if self._settings["fullscreen"] else "关闭"
        if _pygame_available:
            try:
                flags = pygame.FULLSCREEN if self._settings["fullscreen"] else 0
                w, h = _RESOLUTIONS[self._settings["resolution_idx"]]
                pygame.display.set_mode((w, h), flags)
            except Exception as e:
                logger.warning(f"切换全屏失败: {e}")

    def _on_save(self) -> None:
        # 应用分辨率（若非全屏则在窗口模式下也调整尺寸）
        if _pygame_available and not self._settings["fullscreen"]:
            try:
                w, h = _RESOLUTIONS[self._settings["resolution_idx"]]
                pygame.display.set_mode((w, h))
            except Exception as e:
                logger.warning(f"应用分辨率失败: {e}")
        self._save_settings()

    def _on_back(self) -> None:
        self._save_settings()
        self.game.state_machine.change(GameState.MAIN_MENU)

    # ── 事件 / 更新 / 渲染 ────────────────────────────

    def handle_event(self, event) -> None:
        for widget in self._widgets:
            if widget.handle_event(event):
                break

    def update(self, dt: float) -> None:
        for widget in self._widgets:
            widget.update(dt)

    def render(self, surface) -> None:
        if not _pygame_available:
            return
        surface.fill(COLOR_BG_DARK)
        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)
