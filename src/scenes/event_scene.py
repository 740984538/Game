"""
随机事件场景 - 对应开发计划 8-11，文档 §7.3 / §4.1.2

进入方式（由 MapNavigationScene 切换）::

    self.game.state_machine.change(
        GameState.EVENT,
        event_id=None,           # 不传则随机选一个
        floor=floor, floor_number=N, character_id=..., daily=..., seed=..., node_id=...,
    )

完成标志（开发计划 8-11）：
  - 显示事件描述文本
  - 显示 2-3 个选项
  - 选择后触发对应效果（获得/失去金币、HP、遗物等）
  - 显示结果后返回地图

事件配置（config/events/random_events.yaml）::

    - id: mysterious_merchant
      name: "神秘商人"
      description: "..."
      choices:
        - text: "..."
          condition: "gold >= 50"   # 可选；不满足时按钮禁用
          outcome:
            gold: -50               # 数值：增减金币
            hp_cost: 10             # 扣血（直接修改 health）
            hp_percent_cost: 0.3    # 按 max_health 比例扣血
            reward: random_relic    # random_relic / epic_relic / legendary_relic / random_card
            reward:                 # 也可传字典
              type: gold
              amount_min: 50
              amount_max: 100
        - text: "离开"
          outcome: null             # 无副作用
"""
from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional, TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

from src.scenes.base_scene import BaseScene
from src.ui.widgets.button import Button
from src.ui.widgets.label import Label
from src.ui.widgets.panel import Panel
from src.utils.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_DIVIDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_WHITE, COLOR_GOLD, COLOR_DANGER, COLOR_HEAL,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)
from src.utils.enums import GameState

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


# ── 布局 ────────────────────────────────────────────────────────────────────

_PANEL_W = 760
_PANEL_H = 500
_PANEL_X = (SCREEN_WIDTH - _PANEL_W) // 2
_PANEL_Y = (SCREEN_HEIGHT - _PANEL_H) // 2

_CHOICE_BTN_W = 600
_CHOICE_BTN_H = 60


class EventScene(BaseScene):
    """随机事件场景"""

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self._widgets: list = []
        self._return_kwargs: dict = {}
        self._event_data: Dict = {}
        self._rng: Optional[random.Random] = None
        self._showing_result: bool = False
        self._result_label: Optional[Label] = None

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def enter(self, **kwargs) -> None:
        self._return_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("room_type", "node_id", "event_id")
        }
        seed = kwargs.get("seed", 0)
        floor_number = kwargs.get("floor_number", 1)
        node_id = kwargs.get("node_id", 0)
        self._rng = random.Random(seed * 100 + floor_number * 13 + node_id * 7 + 71)

        # 加载事件
        event_id = kwargs.get("event_id")
        self._event_data = self._load_event(event_id)
        self._showing_result = False
        self._widgets.clear()
        self._build_ui()
        logger.info("进入事件场景: %s", self._event_data.get("id", "?"))

    def exit(self) -> None:
        self._widgets.clear()
        logger.info("离开事件场景")

    # ── 数据加载 ──────────────────────────────────────────────────────────

    def _load_event(self, event_id: Optional[str]) -> dict:
        try:
            from src.data.config_loader import ConfigLoader
            events = ConfigLoader().load_events()
        except Exception as exc:
            logger.warning("加载事件配置失败: %s", exc)
            events = []

        if not events:
            return {
                "id": "default",
                "name": "空旷的房间",
                "description": "一个空荡荡的房间，似乎没什么特别的。",
                "choices": [{"text": "离开", "outcome": None}],
            }

        if event_id:
            for e in events:
                if e.get("id") == event_id:
                    return e
        if self._rng:
            return self._rng.choice(events)
        return events[0]

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 背景
        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK,
            border_color=None, border_width=0,
        )
        self._widgets.append(bg)

        # 中央面板
        panel = Panel(
            _PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_TEXT_PRIMARY,
            border_width=2,
            border_radius=10,
        )
        self._widgets.append(panel)

        # 事件名
        title = Label(
            _PANEL_X, _PANEL_Y + 24, _PANEL_W, 40,
            text=self._event_data.get("name", "未知事件"),
            font_size=FONT_SIZE_H1,
            color=COLOR_TEXT_PRIMARY,
            align="center", bold=True,
        )
        self._widgets.append(title)

        # 描述
        desc = Label(
            _PANEL_X + 40, _PANEL_Y + 80,
            _PANEL_W - 80, 100,
            text=self._event_data.get("description", ""),
            font_size=FONT_SIZE_BODY,
            color=COLOR_WHITE,
            align="center", wrap=True,
        )
        self._widgets.append(desc)

        # 分割线
        divider = Panel(
            _PANEL_X + 80, _PANEL_Y + 200, _PANEL_W - 160, 2,
            bg_color=COLOR_DIVIDER, border_color=None, border_width=0,
        )
        self._widgets.append(divider)

        # 选项按钮
        choices = self._event_data.get("choices", [])
        self._build_choice_buttons(choices)

        # 玩家状态条（金币 / HP）
        rs = getattr(self.game, "run_state", None)
        if rs:
            status = f"金币: {rs.gold}    HP: {rs.health}/{rs.max_health}"
        else:
            status = ""
        status_label = Label(
            _PANEL_X, _PANEL_Y + _PANEL_H - 28, _PANEL_W, 22,
            text=status,
            font_size=FONT_SIZE_CAPTION,
            color=COLOR_TEXT_SECONDARY,
            align="center",
        )
        self._widgets.append(status_label)

    def _build_choice_buttons(self, choices: List[dict]) -> None:
        if not choices:
            return

        btn_y_start = _PANEL_Y + 220
        gap = 12
        n = len(choices)
        rs = getattr(self.game, "run_state", None)

        for i, choice in enumerate(choices):
            text = choice.get("text", "选项")
            condition = choice.get("condition")
            enabled = self._check_condition(condition, rs)
            display_text = text if enabled else f"{text} （条件不满足）"

            btn = Button(
                _PANEL_X + (_PANEL_W - _CHOICE_BTN_W) // 2,
                btn_y_start + i * (_CHOICE_BTN_H + gap),
                _CHOICE_BTN_W, _CHOICE_BTN_H,
                text=display_text,
                font_size=FONT_SIZE_BODY,
                on_click=self._make_choice_handler(choice),
            )
            btn.enabled = enabled
            self._widgets.append(btn)

    def _check_condition(self, condition: Optional[str], rs) -> bool:
        """简易条件解析（支持 gold>=N / hp>N / has_relic:id）"""
        if not condition or not rs:
            return True
        cond = condition.strip()
        try:
            if cond.startswith("gold >="):
                return rs.gold >= int(cond.split(">=", 1)[1].strip())
            if cond.startswith("gold >"):
                return rs.gold > int(cond.split(">", 1)[1].strip())
            if cond.startswith("hp >"):
                return rs.health > int(cond.split(">", 1)[1].strip())
            if cond == "has_healing_potion":
                return False  # 暂未实现治疗道具系统
            if cond.startswith("has_relic:"):
                return rs.has_relic(cond.split(":", 1)[1].strip())
        except Exception:
            pass
        return True

    # ── 选项执行 ──────────────────────────────────────────────────────────

    def _make_choice_handler(self, choice: dict):
        def _handler():
            outcome = choice.get("outcome")
            result_text = self._apply_outcome(outcome)
            self._show_result(result_text)
        return _handler

    def _apply_outcome(self, outcome) -> str:
        """
        根据 outcome 修改 RunState，返回结果描述文本。
        """
        if outcome is None:
            return "你转身离开。"

        rs = getattr(self.game, "run_state", None)
        if rs is None:
            return "无可记录的效果。"

        msgs: List[str] = []

        # 金币变动
        gold_delta = int(outcome.get("gold", 0))
        if gold_delta:
            actual = gold_delta if gold_delta < 0 else gold_delta
            rs.add_gold(actual)
            msgs.append(f"金币 {'+' if actual > 0 else ''}{actual}")

        # HP 直接扣
        hp_cost = int(outcome.get("hp_cost", 0))
        if hp_cost:
            taken = rs.take_damage(hp_cost)
            msgs.append(f"失去 {taken} HP")

        # HP 按比例扣
        hp_percent = float(outcome.get("hp_percent_cost", 0))
        if hp_percent > 0:
            cost = max(1, int(rs.max_health * hp_percent))
            taken = rs.take_damage(cost)
            msgs.append(f"失去 {taken} HP（{int(hp_percent*100)}% 上限）")

        # 治疗
        heal = int(outcome.get("heal", 0))
        if heal:
            actual = rs.heal(heal)
            msgs.append(f"恢复 {actual} HP")

        # 奖励
        reward = outcome.get("reward")
        if reward:
            msgs.append(self._grant_reward(reward, rs))

        # 检查死亡
        if not rs.is_alive():
            msgs.append("你倒下了……")

        return "  ".join(m for m in msgs if m) or "（无明显变化）"

    def _grant_reward(self, reward, rs) -> str:
        """处理 reward 字段（字符串或 dict）"""
        from src.entities.relics.relic import RelicRegistry

        # 字符串短代码
        if isinstance(reward, str):
            registry = RelicRegistry.instance()
            if not registry.is_loaded:
                try:
                    registry.load_all()
                except Exception:
                    pass

            if reward == "random_relic":
                relic = self._pick_random_relic(rs, min_rarity="common")
                if relic and rs.add_relic(relic):
                    return f"获得遗物：{relic}"
                return "未能获得遗物"

            if reward == "epic_relic":
                relic = self._pick_random_relic(rs, min_rarity="epic")
                if relic and rs.add_relic(relic):
                    return f"获得史诗遗物：{relic}"
                return "未能获得遗物"

            if reward == "legendary_relic":
                relic = self._pick_random_relic(rs, min_rarity="legendary")
                if relic and rs.add_relic(relic):
                    return f"获得传说遗物：{relic}"
                return "未能获得遗物"

            if reward == "random_card":
                card_id = self._pick_random_card()
                if card_id:
                    rs.add_card(card_id)
                    return f"获得卡牌：{card_id}"
                return "未能获得卡牌"

        # 字典形式
        if isinstance(reward, dict):
            r_type = reward.get("type")
            if r_type == "gold":
                lo = int(reward.get("amount_min", 0))
                hi = int(reward.get("amount_max", lo))
                amount = self._rng.randint(lo, hi) if self._rng else lo
                rs.add_gold(amount)
                return f"获得 {amount} 金币"
            if r_type == "relic":
                rid = reward.get("id")
                if rid and rs.add_relic(rid):
                    return f"获得遗物：{rid}"

        return ""

    def _pick_random_relic(self, rs, min_rarity: str = "common") -> Optional[str]:
        """从未持有的遗物中随机一个"""
        from src.entities.relics.relic import RelicRegistry
        registry = RelicRegistry.instance()
        if not registry.is_loaded:
            try:
                registry.load_all()
            except Exception:
                return None

        rarity_order = ["common", "rare", "epic", "legendary"]
        try:
            min_idx = rarity_order.index(min_rarity)
        except ValueError:
            min_idx = 0

        owned = set(rs.get_relic_ids())
        candidates = [
            r.id for r in registry.all_relics()
            if r.id not in owned
            and rarity_order.index(r.rarity) >= min_idx
        ]
        if not candidates:
            return None
        if self._rng:
            return self._rng.choice(candidates)
        return candidates[0]

    def _pick_random_card(self) -> Optional[str]:
        try:
            from src.data.config_loader import ConfigLoader
            cards = ConfigLoader().load_all_cards()
            ids = [
                cid for cid, cfg in cards.items()
                if cfg.get("type") not in ("cursed",)
            ]
            if ids and self._rng:
                return self._rng.choice(ids)
            return ids[0] if ids else None
        except Exception:
            return None

    # ── 结果展示 ──────────────────────────────────────────────────────────

    def _show_result(self, text: str) -> None:
        self._showing_result = True
        # 移除选项按钮，仅保留背景/描述
        # 简化处理：直接重建 widgets
        self._widgets.clear()

        bg = Panel(
            0, 0, SCREEN_WIDTH, SCREEN_HEIGHT,
            bg_color=COLOR_BG_DARK,
            border_color=None, border_width=0,
        )
        self._widgets.append(bg)

        panel = Panel(
            _PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H,
            bg_color=COLOR_BG_LIGHT,
            border_color=COLOR_GOLD,
            border_width=2,
            border_radius=10,
        )
        self._widgets.append(panel)

        title = Label(
            _PANEL_X, _PANEL_Y + 24, _PANEL_W, 40,
            text=self._event_data.get("name", ""),
            font_size=FONT_SIZE_H2,
            color=COLOR_TEXT_PRIMARY,
            align="center", bold=True,
        )
        self._widgets.append(title)

        result_label = Label(
            _PANEL_X + 40, _PANEL_Y + 100,
            _PANEL_W - 80, _PANEL_H - 200,
            text=text,
            font_size=FONT_SIZE_H3,
            color=COLOR_GOLD,
            align="center", wrap=True,
        )
        self._widgets.append(result_label)

        # 状态行
        rs = getattr(self.game, "run_state", None)
        if rs:
            status = f"金币: {rs.gold}    HP: {rs.health}/{rs.max_health}"
            status_label = Label(
                _PANEL_X, _PANEL_Y + _PANEL_H - 90, _PANEL_W, 22,
                text=status,
                font_size=FONT_SIZE_BODY,
                color=COLOR_TEXT_SECONDARY,
                align="center",
            )
            self._widgets.append(status_label)

        # 继续按钮
        continue_btn = Button(
            _PANEL_X + (_PANEL_W - 220) // 2, _PANEL_Y + _PANEL_H - 64,
            220, 44,
            text="继续",
            font_size=FONT_SIZE_H3,
            on_click=self._return_to_map,
            normal_bg=(40, 70, 40),
            hover_bg=(60, 110, 60),
            border_color=(80, 180, 80),
        )
        self._widgets.append(continue_btn)

    # ── 返回 ──────────────────────────────────────────────────────────────

    def _return_to_map(self) -> None:
        # 死亡判定
        rs = getattr(self.game, "run_state", None)
        if rs and not rs.is_alive():
            rs.end_run()
            self.game.state_machine.change(
                GameState.GAME_OVER,
                reason="event",
            )
            return
        self.game.state_machine.change(GameState.MAP_NAVIGATION, **self._return_kwargs)

    # ── 事件 / 更新 / 渲染 ────────────────────────────────────────────────

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._return_to_map()
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
