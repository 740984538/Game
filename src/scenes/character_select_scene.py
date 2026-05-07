"""
角色选择场景
对应开发计划 §3-6（角色卡片 UI）/ §3-7（角色选择交互）
"""
from __future__ import annotations
import logging
from typing import List, Optional, TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.scenes.base_scene import BaseScene
from src.ui.widgets.button import Button
from src.ui.widgets.label import Label
from src.ui.widgets.panel import Panel
from src.ui.widgets.character_card import CharacterCard
from src.entities.player.character_stats import CharacterData, CharacterRegistry
from src.utils.constants import (
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_TEXT_PRIMARY,
    COLOR_WHITE, COLOR_DIVIDER, COLOR_TEXT_SECONDARY, COLOR_GOLD,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY,
    SCREEN_WIDTH, SCREEN_HEIGHT,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)

# ── 布局常量 ──────────────────────────────────────────
_CARD_W = 320
_CARD_H = 100
_CARD_GAP = 14
_CENTER_X = SCREEN_WIDTH // 2

# 角色机制简介映射（从配置的 special_mechanic 字段翻译为可读中文）
_MECHANIC_NAMES = {
    "block_system": "格挡系统：以防代攻",
    "combo_system": "连击系统：连续攻击增伤",
    "spell_power": "法术系统：强化法术伤害",
    "trap_system": "陷阱系统：远程持续伤害",
    "summon_system": "召唤系统：亡灵军团作战",
}


class CharacterSelectScene(BaseScene):
    """
    角色选择场景：
    - 展示所有角色卡片（已解锁 + 未解锁）
    - 点击卡片选中（高亮）
    - 确认按钮进入地图场景
    - 返回按钮回到主菜单
    - 支持每日挑战模式（由 enter(daily=True) 传入）
    """

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._cards: List[CharacterCard] = []
        self._selected_card: Optional[CharacterCard] = None
        self._confirm_btn: Optional[Button] = None
        self._info_label: Optional[Label] = None
        self._daily_mode = False
        self._built = False

        # 元进度数据（解锁角色列表）
        self._unlocked_ids: List[str] = ["knight"]

    # ── 场景生命周期 ──────────────────────────────────

    def enter(self, **kwargs) -> None:
        self._daily_mode = kwargs.get("daily", False)

        # 加载角色注册表
        registry = CharacterRegistry.instance()
        if not registry.is_loaded:
            registry.load_all()

        # 加载元进度（获取已解锁角色列表）
        self._load_unlocked_characters()

        if not self._built:
            self._build_ui()
            self._built = True
        else:
            self._rebuild_cards()

        # 重置选择状态
        self._selected_card = None
        for card in self._cards:
            card.selected = False
        if self._confirm_btn:
            self._confirm_btn.enabled = False
        if self._info_label:
            self._info_label.text = "请选择一个角色"

        mode_str = "每日挑战" if self._daily_mode else "普通"
        logger.info("进入角色选择场景 (模式: %s)", mode_str)

    def exit(self) -> None:
        logger.info("离开角色选择场景")

    # ── 元进度 ────────────────────────────────────────

    def _load_unlocked_characters(self) -> None:
        """从存档读取已解锁角色列表"""
        try:
            from src.data.save_manager import SaveManager
            sm = SaveManager()
            meta = sm.load_meta_progress()
            self._unlocked_ids = meta.unlocked_characters
            sm.close()
        except Exception as e:
            logger.warning("加载元进度失败: %s，使用默认解锁", e)
            self._unlocked_ids = ["knight"]

    # ── UI 构建 ────────────────────────────────────────

    def _build_ui(self) -> None:
        """构建完整 UI"""
        # ── 背景 ──
        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK, border_color=None, border_width=0,
        )
        self._widgets.append(bg)

        # ── 装饰侧边条 ──
        left_bar = Panel(
            0, 0, 6, SCREEN_HEIGHT,
            bg_color=COLOR_TEXT_PRIMARY, border_color=None, border_width=0,
        )
        right_bar = Panel(
            SCREEN_WIDTH - 6, 0, 6, SCREEN_HEIGHT,
            bg_color=COLOR_TEXT_PRIMARY, border_color=None, border_width=0,
        )
        self._widgets.extend([left_bar, right_bar])

        # ── 标题 ──
        title_text = "每日挑战 - 选择角色" if self._daily_mode else "选择角色"
        title_label = Label(
            _CENTER_X - 300, 30, 600, 50,
            text=title_text,
            font_size=FONT_SIZE_H1,
            color=COLOR_TEXT_PRIMARY if not self._daily_mode else COLOR_GOLD,
            align="center", bold=True,
        )
        self._widgets.append(title_label)

        # ── 分割线 ──
        divider = Panel(
            _CENTER_X - 150, 86, 300, 2,
            bg_color=COLOR_DIVIDER, border_color=None, border_width=0,
        )
        self._widgets.append(divider)

        # ── 角色卡片列表 ──
        self._build_cards()

        # ── 信息标签（选中角色的描述） ──
        self._info_label = Label(
            _CENTER_X - 300, SCREEN_HEIGHT - 120, 600, 30,
            text="请选择一个角色",
            font_size=FONT_SIZE_BODY,
            color=COLOR_TEXT_SECONDARY, align="center",
        )
        self._widgets.append(self._info_label)

        # ── 底部按钮 ──
        btn_w = 200
        btn_h = 48
        btn_y = SCREEN_HEIGHT - 76

        self._confirm_btn = Button(
            _CENTER_X - btn_w - 16, btn_y, btn_w, btn_h,
            text="确认选择",
            font_size=FONT_SIZE_H3,
            on_click=self._on_confirm,
            normal_bg=(30, 70, 30),
            hover_bg=(50, 110, 50),
            border_color=(60, 180, 60),
        )
        self._confirm_btn.enabled = False
        self._widgets.append(self._confirm_btn)

        back_btn = Button(
            _CENTER_X + 16, btn_y, btn_w, btn_h,
            text="返回主菜单",
            font_size=FONT_SIZE_H3,
            on_click=self._on_back,
        )
        self._widgets.append(back_btn)

    def _build_cards(self) -> None:
        """根据角色注册表生成卡片组件"""
        registry = CharacterRegistry.instance()
        characters = registry.all_characters()

        self._cards.clear()

        # 计算卡片起始位置（居中排列，最多两列）
        cols = 2
        total = len(characters)
        rows = (total + cols - 1) // cols

        grid_w = cols * _CARD_W + (cols - 1) * _CARD_GAP
        grid_h = rows * _CARD_H + (rows - 1) * _CARD_GAP
        start_x = _CENTER_X - grid_w // 2
        start_y = 110

        for idx, char_data in enumerate(characters):
            col = idx % cols
            row = idx // cols

            card_x = start_x + col * (_CARD_W + _CARD_GAP)
            card_y = start_y + row * (_CARD_H + _CARD_GAP)

            is_locked = char_data.id not in self._unlocked_ids
            mechanic_desc = _MECHANIC_NAMES.get(
                char_data.special_mechanic, char_data.special_mechanic
            )

            card = CharacterCard(
                card_x, card_y, _CARD_W, _CARD_H,
                char_id=char_data.id,
                name=char_data.name,
                role=char_data.role,
                hp=char_data.base_stats.health,
                mechanic=mechanic_desc,
                unlock_cost=char_data.unlock_cost,
                locked=is_locked,
                on_click=self._on_card_click,
            )
            self._cards.append(card)
            self._widgets.append(card)

    def _rebuild_cards(self) -> None:
        """重建卡片（重进场景时刷新解锁状态）"""
        # 移除旧卡片
        for card in self._cards:
            if card in self._widgets:
                self._widgets.remove(card)
        self._build_cards()

    # ── 交互回调 ──────────────────────────────────────

    def _on_card_click(self, card: CharacterCard) -> None:
        """点击卡片的回调"""
        # 锁定角色不可选
        if card.locked:
            if self._info_label:
                self._info_label.text = f"该角色需要 {card._unlock_cost} 灵魂碎片解锁"
                self._info_label.color = COLOR_GOLD
            return

        # 取消之前的选择
        if self._selected_card is not None:
            self._selected_card.selected = False

        # 选中当前卡片
        card.selected = True
        self._selected_card = card

        # 更新信息标签：显示角色描述
        registry = CharacterRegistry.instance()
        char_data = registry.get(card.char_id)
        if char_data and self._info_label:
            self._info_label.text = char_data.description
            self._info_label.color = COLOR_WHITE

        # 启用确认按钮
        if self._confirm_btn:
            self._confirm_btn.enabled = True

        logger.info("选中角色: %s", card.char_id)

    def _on_confirm(self) -> None:
        """确认选择，进入地图场景"""
        if self._selected_card is None:
            return

        char_id = self._selected_card.char_id
        logger.info("确认选择角色: %s (每日挑战=%s)", char_id, self._daily_mode)

        # 初始化跨场景的整局状态
        try:
            import random as _random
            seed = 0
            if self._daily_mode:
                from src.generation.seed_manager import SeedManager
                seed = SeedManager().daily_seed()
            else:
                seed = _random.randint(1, 999999999)
            self.game.run_state.start_new_run(
                character_id=char_id, seed=seed, daily=self._daily_mode,
            )
        except Exception as exc:
            logger.warning("初始化 RunState 失败: %s", exc)

        self.game.state_machine.change(
            GameState.MAP_NAVIGATION,
            character_id=char_id,
            daily=self._daily_mode,
        )

    def _on_back(self) -> None:
        """返回主菜单"""
        self.game.state_machine.change(GameState.MAIN_MENU)

    # ── 事件 / 更新 / 渲染 ────────────────────────────

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return
        # ESC 返回主菜单
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_back()
            return
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
