"""
战斗场景 - 对应文档 §4.2
实现开发计划:
  5-3: 战斗场景布局 (玩家区、敌人区、手牌区、能量显示)
  5-4: 玩家显示 (角色图像/占位图、血条、能量)
  5-5: 敌人显示 (敌人图像/占位图、血条、意图图标)
"""
from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

try:
    import pygame
    _pygame_available = True
except ImportError:
    _pygame_available = False

try:
    import esper
    _esper_available = True
except ImportError:
    _esper_available = False

from src.scenes.base_scene import BaseScene
from src.ecs.components import (
    Position, Sprite, Health, Stats, Block, Energy,
    PlayerTag, EnemyTag, BuffList, IntentDisplay,
    BossController, CardHolder,
)
from src.ecs.entities import EntityFactory
from src.data.config_loader import ConfigLoader
from src.core.event_manager import event_manager
from src.systems.loot_system import LootManager
from src.generation.difficulty_scaler import DifficultyScaler
from src.ui.widgets.button import Button
from src.ui.widgets.label import Label
from src.ui.widgets.panel import Panel
from src.utils.constants import (
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_TEXT_PRIMARY,
    COLOR_WHITE, COLOR_DIVIDER, COLOR_TEXT_SECONDARY,
    COLOR_GOLD, COLOR_DANGER, COLOR_HEAL, COLOR_EPIC,
    COLOR_BLACK,
    FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    SCREEN_WIDTH, SCREEN_HEIGHT,
)
from src.utils.enums import GameState, RoomType

if TYPE_CHECKING:
    from src.core.game import Game

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 5-3: 战斗场景布局常量
# ═══════════════════════════════════════════════════════════════════════════════

# 整体区域划分 (1280 x 720)
_HEADER_H = 50          # 顶部信息栏高度
_HAND_AREA_H = 160      # 底部手牌区高度
_BATTLE_AREA_H = SCREEN_HEIGHT - _HEADER_H - _HAND_AREA_H  # 510 = 战斗区

# 玩家区 (左下)
_PLAYER_AREA_X = 80
_PLAYER_AREA_Y = _HEADER_H + _BATTLE_AREA_H - 200  # 底部偏上
_PLAYER_AREA_W = 300
_PLAYER_AREA_H = 200

# 敌人区 (右上)
_ENEMY_AREA_X = SCREEN_WIDTH - 450
_ENEMY_AREA_Y = _HEADER_H + 40
_ENEMY_AREA_W = 400
_ENEMY_AREA_H = 280

# 能量显示 (左下角)
_ENERGY_X = 30
_ENERGY_Y = SCREEN_HEIGHT - _HAND_AREA_H - 60

# 血条尺寸
_HP_BAR_W = 80
_HP_BAR_H = 10
_HP_BAR_BG = (40, 40, 40)
_HP_BAR_FG = (40, 180, 40)
_HP_BAR_DANGER = (200, 40, 40)
_HP_BAR_BOSS = (180, 30, 30)

# 格挡条
_BLOCK_COLOR = (80, 140, 200)

# 意图图标颜色
_INTENT_COLORS: Dict[str, Tuple[int, int, int]] = {
    "attack": (220, 60, 60),
    "defend": (60, 140, 220),
    "buff": (220, 180, 40),
    "debuff": (160, 60, 200),
    "unknown": (120, 120, 120),
}


# ═══════════════════════════════════════════════════════════════════════════════
# CombatScene
# ═══════════════════════════════════════════════════════════════════════════════

class CombatScene(BaseScene):
    """
    核心战斗场景。

    职责:
    - 初始化 ECS 世界，生成玩家和敌人实体
    - 渲染战斗布局 (5-3)
    - 渲染玩家 (5-4): 占位图、血条、能量
    - 渲染敌人 (5-5): 占位图、血条、意图图标
    - 战斗结束后根据结果切换场景
    """

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        # ECS 世界
        self._world: Optional[object] = None
        self._factory: Optional[EntityFactory] = None

        # 实体引用
        self._player_entity: int = -1
        self._enemy_entities: List[int] = []

        # 场景上下文
        self._floor = None
        self._floor_number: int = 1
        self._character_id: str = "knight"
        self._room_type: Optional[RoomType] = None
        self._node_id: int = -1
        self._seed: int = 0
        self._daily: bool = False

        # UI 组件
        self._widgets: list = []
        self._built: bool = False

        # 字体缓存
        self._font_body = None
        self._font_caption = None
        self._font_h3 = None

        # 8-9: BOSS 阶段切换提示（横幅）
        self._phase_banner_text: str = ""
        self._phase_banner_timer: float = 0.0  # 秒

        # 8-3 / 8-8: 战利品管理器（按 RunState seed 初始化）
        self._loot_manager: Optional[LootManager] = None

        # 8-10: 难度缩放
        self._scaler: DifficultyScaler = DifficultyScaler.from_config()

        # 事件订阅是否已注册
        self._events_subscribed: bool = False

    # ══════════════════════════════════════════════════════════════════════
    # 场景生命周期
    # ══════════════════════════════════════════════════════════════════════

    def enter(self, **kwargs) -> None:
        """
        进入战斗场景。
        kwargs:
            floor: Floor         - 楼层数据
            floor_number: int    - 楼层编号
            character_id: str    - 角色 ID
            room_type: RoomType  - 房间类型 (COMBAT/ELITE/BOSS)
            node_id: int         - 当前节点 ID
            seed: int            - 随机种子
        """
        self._floor = kwargs.get("floor")
        self._floor_number = kwargs.get("floor_number", 1)
        self._character_id = kwargs.get("character_id", "knight")
        self._room_type = kwargs.get("room_type", RoomType.COMBAT)
        self._node_id = kwargs.get("node_id", -1)
        self._seed = kwargs.get("seed", 0)
        self._daily = kwargs.get("daily", False)

        # 8-3 / 8-8: 初始化战利品管理器（按种子+楼层稳定）
        import random as _rnd
        loot_seed = self._seed * 1000 + self._floor_number * 31 + self._node_id
        self._loot_manager = LootManager(rng=_rnd.Random(loot_seed))
        self._loot_manager.set_context(
            floor_number=self._floor_number,
            room_type=self._room_type.value if self._room_type else "combat",
        )

        # 8-9: 重置 BOSS 阶段横幅
        self._phase_banner_text = ""
        self._phase_banner_timer = 0.0

        # 注册事件订阅
        self._subscribe_events()

        # 初始化 ECS
        self._init_world()

        # 构建 UI
        if not self._built:
            self._build_ui()
            self._built = True

        self._update_header()

        logger.info(
            "进入战斗: 楼层=%d, 角色=%s, 类型=%s",
            self._floor_number, self._character_id,
            self._room_type.value if self._room_type else "unknown"
        )

    def exit(self) -> None:
        """离开战斗场景，清理 ECS 世界"""
        if self._world and _esper_available:
            self._world.clear_database()
        self._player_entity = -1
        self._enemy_entities.clear()
        self._unsubscribe_events()
        logger.info("离开战斗场景")

    # ══════════════════════════════════════════════════════════════════════
    # ECS 初始化
    # ══════════════════════════════════════════════════════════════════════

    def _init_world(self) -> None:
        """创建 ECS 世界并生成实体"""
        if not _esper_available:
            return

        self._world = esper.World()
        self._factory = EntityFactory(self._world)

        # 加载角色配置并创建玩家
        config_loader = ConfigLoader()
        char_config = config_loader.load_character(self._character_id)

        # 玩家位置 (左下区域居中)
        px = _PLAYER_AREA_X + _PLAYER_AREA_W // 2
        py = _PLAYER_AREA_Y + _PLAYER_AREA_H // 2
        self._player_entity = self._factory.create_player(char_config, x=px, y=py)

        # 生成敌人
        self._spawn_enemies(config_loader)

    def _spawn_enemies(self, config_loader: ConfigLoader) -> None:
        """根据房间类型生成敌人（含 8-10 难度缩放）"""
        all_enemies = config_loader.load_all_enemies()
        difficulty = self._get_difficulty()

        if self._room_type == RoomType.BOSS:
            # BOSS 战: 生成对应楼层 BOSS
            boss_id = self._get_boss_id()
            boss_cfg = all_enemies.get(boss_id)
            if boss_cfg:
                # 8-10: 应用难度缩放（仅 base_stats，BOSS 有 phases 不需要缩放）
                scaled = self._scaler.scale_enemy_config(
                    boss_cfg, floor=self._floor_number, difficulty=difficulty,
                )
                bx = _ENEMY_AREA_X + _ENEMY_AREA_W // 2
                by = _ENEMY_AREA_Y + _ENEMY_AREA_H // 2
                eid = self._factory.create_boss(scaled, x=bx, y=by)
                self._enemy_entities.append(eid)
        else:
            # 普通/精英: 从敌人池中选取
            enemy_pool = self._get_enemy_pool(all_enemies)
            count = self._get_enemy_count()

            for i in range(count):
                enemy_cfg = random.choice(enemy_pool) if enemy_pool else None
                if enemy_cfg:
                    # 8-10: 应用难度缩放
                    scaled = self._scaler.scale_enemy_config(
                        enemy_cfg, floor=self._floor_number, difficulty=difficulty,
                    )
                    # 均匀排列敌人
                    spacing = _ENEMY_AREA_W // (count + 1)
                    ex = _ENEMY_AREA_X + spacing * (i + 1)
                    ey = _ENEMY_AREA_Y + _ENEMY_AREA_H // 2 + random.randint(-20, 20)
                    eid = self._factory.create_enemy(scaled, x=ex, y=ey)
                    self._enemy_entities.append(eid)

    def _get_difficulty(self) -> int:
        rs = getattr(self.game, "run_state", None)
        return rs.difficulty if rs else 1

    def _get_boss_id(self) -> str:
        """获取当前楼层的 BOSS ID"""
        try:
            config_loader = ConfigLoader()
            floor_cfg = config_loader.load_floor_config(self._floor_number)
            return floor_cfg.get("boss_id", "bone_king")
        except Exception:
            return "bone_king"

    def _get_enemy_pool(self, all_enemies: dict) -> List[dict]:
        """获取可用敌人池"""
        if self._room_type == RoomType.ELITE:
            return [e for e in all_enemies.values()
                    if e.get("type") == "elite"]
        return [e for e in all_enemies.values()
                if e.get("type") == "common"]

    def _get_enemy_count(self) -> int:
        """根据房间类型确定敌人数量"""
        if self._room_type == RoomType.ELITE:
            return 1
        return random.randint(1, 3)

    # ══════════════════════════════════════════════════════════════════════
    # UI 构建
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """构建战斗场景 UI 组件"""
        # 结束回合按钮
        end_turn_btn = Button(
            SCREEN_WIDTH - 160, SCREEN_HEIGHT - _HAND_AREA_H - 48,
            140, 40,
            text="结束回合",
            font_size=FONT_SIZE_BODY,
            on_click=self._on_end_turn,
            normal_bg=(50, 30, 30),
            hover_bg=(80, 40, 40),
            border_color=(180, 60, 60),
        )
        self._widgets.append(end_turn_btn)

        # 8-8: 临时调试按钮 — 战斗胜利 / 失败（在完整回合制接入前用于流程联调）
        self._win_btn = Button(
            SCREEN_WIDTH - 320, SCREEN_HEIGHT - _HAND_AREA_H - 48,
            150, 40,
            text="[调试] 战斗胜利",
            font_size=FONT_SIZE_CAPTION,
            on_click=self._debug_win,
            normal_bg=(20, 60, 30),
            hover_bg=(30, 100, 50),
            border_color=(80, 180, 80),
        )
        self._widgets.append(self._win_btn)

        self._lose_btn = Button(
            SCREEN_WIDTH - 480, SCREEN_HEIGHT - _HAND_AREA_H - 48,
            150, 40,
            text="[调试] 战斗失败",
            font_size=FONT_SIZE_CAPTION,
            on_click=self._debug_lose,
            normal_bg=(60, 20, 20),
            hover_bg=(120, 30, 30),
            border_color=COLOR_DANGER,
        )
        self._widgets.append(self._lose_btn)

        # 顶部信息标签
        self._header_label = Label(
            SCREEN_WIDTH // 2 - 200, 10, 400, 30,
            text="战斗",
            font_size=FONT_SIZE_H3,
            color=COLOR_TEXT_PRIMARY,
            align="center", bold=True,
        )
        self._widgets.append(self._header_label)

        # 楼层标签
        self._floor_label = Label(
            20, 14, 200, 24,
            text="",
            font_size=FONT_SIZE_CAPTION,
            color=COLOR_TEXT_SECONDARY,
        )
        self._widgets.append(self._floor_label)

    def _update_header(self) -> None:
        """更新顶部标题"""
        if self._room_type == RoomType.BOSS:
            title = "BOSS 战"
        elif self._room_type == RoomType.ELITE:
            title = "精英战斗"
        else:
            title = "战斗"
        if hasattr(self, "_header_label") and self._header_label:
            self._header_label.text = title
        if hasattr(self, "_floor_label") and self._floor_label:
            self._floor_label.text = f"第 {self._floor_number} 层"

    # ══════════════════════════════════════════════════════════════════════
    # 字体懒加载
    # ══════════════════════════════════════════════════════════════════════

    def _get_font_body(self):
        if self._font_body is None and _pygame_available:
            self._font_body = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_BODY
            )
        return self._font_body

    def _get_font_caption(self):
        if self._font_caption is None and _pygame_available:
            self._font_caption = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_CAPTION
            )
        return self._font_caption

    def _get_font_h3(self):
        if self._font_h3 is None and _pygame_available:
            self._font_h3 = pygame.font.SysFont(
                "microsoftyahei,simhei,arial", FONT_SIZE_H3, bold=True
            )
        return self._font_h3

    # ══════════════════════════════════════════════════════════════════════
    # 事件处理
    # ══════════════════════════════════════════════════════════════════════

    def handle_event(self, event) -> None:
        if not _pygame_available:
            return

        # ESC → 暂停
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_pause()
            return

        # UI 组件
        for widget in self._widgets:
            if widget.handle_event(event):
                break

    def _on_end_turn(self) -> None:
        """结束回合 (占位: 后续由回合制系统驱动)"""
        logger.info("结束回合")

    def _on_pause(self) -> None:
        """暂停"""
        self.game.state_machine.change(
            GameState.PAUSE,
            return_state=GameState.COMBAT,
            return_kwargs=self._build_return_kwargs(),
        )

    # ══════════════════════════════════════════════════════════════════════
    # 8-8: 战斗结束 / 楼层切换
    # ══════════════════════════════════════════════════════════════════════

    def _build_return_kwargs(self) -> dict:
        """构造返回上一个场景所需的 kwargs（保留楼层 / 角色 / 种子）"""
        return {
            "floor": self._floor,
            "floor_number": self._floor_number,
            "character_id": self._character_id,
            "daily": self._daily,
            "seed": self._seed,
        }

    def _subscribe_events(self) -> None:
        if self._events_subscribed:
            return
        event_manager.subscribe("on_battle_win", self._on_battle_win)
        event_manager.subscribe("on_battle_lose", self._on_battle_lose)
        event_manager.subscribe("on_boss_phase_change", self._on_boss_phase_change)
        self._events_subscribed = True

    def _unsubscribe_events(self) -> None:
        if not self._events_subscribed:
            return
        event_manager.unsubscribe("on_battle_win", self._on_battle_win)
        event_manager.unsubscribe("on_battle_lose", self._on_battle_lose)
        event_manager.unsubscribe("on_boss_phase_change", self._on_boss_phase_change)
        self._events_subscribed = False

    def _debug_win(self) -> None:
        """调试入口：直接判定战斗胜利（在完整回合制接入前用于流程联调）"""
        logger.info("[调试] 触发战斗胜利")
        event_manager.publish(
            "on_battle_win",
            room_type=self._room_type.value if self._room_type else "combat",
            floor_number=self._floor_number,
        )

    def _debug_lose(self) -> None:
        logger.info("[调试] 触发战斗失败")
        event_manager.publish("on_battle_lose")

    def _on_battle_win(self, **kwargs) -> None:
        """
        战斗胜利后的处理：
          1. 同步 ECS 玩家 HP -> RunState
          2. 生成战利品（金币 / 精华 / 遗物）并累加到 RunState
          3. 根据房间类型选择跳转：
             - BOSS（最终楼层）-> VICTORY
             - BOSS（非最终）   -> RELIC_SELECT (3 选 1) -> 下一层 MAP_NAVIGATION
             - ELITE / 有遗物候选 -> RELIC_SELECT (1 张) -> MAP_NAVIGATION
             - 普通战斗         -> MAP_NAVIGATION
        """
        logger.info("CombatScene: 收到 on_battle_win")
        self._sync_player_to_run_state()
        room_kind = self._room_type.value if self._room_type else "combat"
        rs = getattr(self.game, "run_state", None)

        # 累加战斗统计
        if rs:
            rs.record_combat_result(
                victory=True,
                room_type=room_kind,
                kills=len(self._enemy_entities),
            )

        # 生成战利品
        reward = self._roll_battle_reward(room_kind)

        # 应用金币 / 精华
        if rs and reward:
            rs.add_gold(reward.get("gold", 0))
            rs.add_essence(reward.get("essence", 0))

        # 标记节点已访问 / 清理（地图后续刷新可读）
        if self._floor and self._node_id >= 0:
            try:
                self._floor.mark_node_visited(self._node_id)
            except Exception:
                pass

        # ── 决定下一个场景 ──
        is_boss = (self._room_type == RoomType.BOSS)
        is_final_boss = is_boss and self._is_final_floor()

        if is_final_boss:
            # 最终 BOSS -> 胜利
            if rs:
                rs.end_run()
            self.game.state_machine.change(GameState.VICTORY)
            return

        relic_choices = (reward or {}).get("relic_choices", [])

        if is_boss:
            # 普通 BOSS：3 选 1 后进入下一层
            self._enter_relic_select(relic_choices, advance_floor=True)
        elif relic_choices:
            # 精英或随机掉落：可能 1 选或 3 选
            if len(relic_choices) == 1:
                # 直接获得
                if rs:
                    rs.add_relic(relic_choices[0])
                self._save_run_progress()
                self._return_to_map(advance_floor=False)
            else:
                self._enter_relic_select(relic_choices, advance_floor=False)
        else:
            # 普通战斗无掉落
            self._save_run_progress()
            self._return_to_map(advance_floor=False)

    def _save_run_progress(self) -> None:
        """阶段 9-2：战斗结算后自动存档；失败/胜利时由相应回调清理。"""
        sm = getattr(self.game, "save_manager", None)
        rs = getattr(self.game, "run_state", None)
        if sm is None or rs is None or not rs.active:
            return
        try:
            model = rs.to_run_state_model()
            sm.save_run_state(model)
            logger.debug("已自动存档：floor=%d hp=%d", rs.current_floor, rs.health)
        except Exception as exc:
            logger.warning("自动存档失败: %s", exc)

    def _on_battle_lose(self, **kwargs) -> None:
        """战斗失败：清掉当局存档并跳转到 GameOver"""
        logger.info("CombatScene: 收到 on_battle_lose")
        rs = getattr(self.game, "run_state", None)
        killed_by = ""
        if self._enemy_entities and self._world and _esper_available:
            try:
                first = self._enemy_entities[0]
                tag = self._world.component_for_entity(first, EnemyTag)
                killed_by = tag.name
            except Exception:
                pass
        if rs:
            rs.record_combat_result(
                victory=False,
                room_type=self._room_type.value if self._room_type else "combat",
                killed_by=killed_by,
            )
            rs.health = 0
            rs.end_run()
        # 阶段 9-2：删除当局存档
        sm = getattr(self.game, "save_manager", None)
        if sm is not None:
            try:
                sm.delete_run_state()
            except Exception:
                pass
        self.game.state_machine.change(
            GameState.GAME_OVER,
            reason="death",
        )

    def _on_boss_phase_change(self, **kwargs) -> None:
        """8-9: BOSS 阶段切换 → 顶部弹出横幅 3 秒"""
        boss_name = kwargs.get("boss_name", "BOSS")
        new_phase = kwargs.get("new_phase", 0)
        description = kwargs.get("description", "")
        self._phase_banner_text = (
            f"{boss_name} 进入第 {new_phase} 阶段：{description}"
        )
        self._phase_banner_timer = 3.0
        logger.info("BOSS 阶段横幅: %s", self._phase_banner_text)

    def _roll_battle_reward(self, room_kind: str) -> dict:
        if not self._loot_manager:
            return {}
        try:
            return self._loot_manager.roll_combat_reward(
                room_kind, floor_number=self._floor_number,
            )
        except Exception as exc:
            logger.warning("生成战利品失败: %s", exc)
            return {}

    def _sync_player_to_run_state(self) -> None:
        """战斗结束时把 ECS 玩家 HP 同步回 RunState"""
        rs = getattr(self.game, "run_state", None)
        if rs is None or not self._world or not _esper_available:
            return
        if self._player_entity < 0:
            return
        try:
            hp = self._world.component_for_entity(self._player_entity, Health)
            rs.health = hp.current
            rs.max_health = hp.maximum
        except Exception:
            pass

    def _is_final_floor(self) -> bool:
        """是否为最后一层（默认 5 层为终点，可由 game_config 覆盖）"""
        try:
            cfg = ConfigLoader().load_game_config()
            total = int(cfg.get("gameplay", {}).get("floors_per_run", 5))
        except Exception:
            total = 5
        return self._floor_number >= total

    def _enter_relic_select(self, relic_choices: List[str],
                            advance_floor: bool) -> None:
        """跳转到遗物选择场景，选择完后回到地图"""
        return_kwargs = self._build_return_kwargs()
        if advance_floor:
            return_kwargs["floor_number"] = self._floor_number + 1
            return_kwargs.pop("floor", None)  # 强制重新生成下一层

        rs = getattr(self.game, "run_state", None)

        def _on_pick(picked_relic_id):
            if picked_relic_id and rs:
                rs.add_relic(picked_relic_id)
            # 阶段 9-2：选完遗物再存档（会捕获新拿到的遗物）
            self._save_run_progress()

        if advance_floor and rs:
            rs.advance_floor()

        self.game.state_machine.change(
            GameState.RELIC_SELECT,
            relic_pool=relic_choices,
            return_state=GameState.MAP_NAVIGATION,
            return_kwargs=return_kwargs,
            on_pick=_on_pick,
        )

    def _return_to_map(self, advance_floor: bool) -> None:
        return_kwargs = self._build_return_kwargs()
        rs = getattr(self.game, "run_state", None)
        if advance_floor:
            if rs:
                rs.advance_floor()
            return_kwargs["floor_number"] = self._floor_number + 1
            return_kwargs.pop("floor", None)
        self.game.state_machine.change(GameState.MAP_NAVIGATION, **return_kwargs)

    # ══════════════════════════════════════════════════════════════════════
    # 更新
    # ══════════════════════════════════════════════════════════════════════

    def update(self, dt: float) -> None:
        """每帧更新"""
        for widget in self._widgets:
            widget.update(dt)
        # 8-9: BOSS 阶段横幅倒计时
        if self._phase_banner_timer > 0:
            self._phase_banner_timer -= dt
            if self._phase_banner_timer <= 0:
                self._phase_banner_text = ""
        # 8-13 / 9-7: 累计游玩时间
        rs = getattr(self.game, "run_state", None)
        if rs and rs.active:
            rs.stats.play_seconds += dt

    # ══════════════════════════════════════════════════════════════════════
    # 渲染 (5-3, 5-4, 5-5)
    # ══════════════════════════════════════════════════════════════════════

    def render(self, surface) -> None:
        if not _pygame_available:
            return

        # 1. 背景
        surface.fill(COLOR_BG_DARK)

        # 2. 布局区域 (5-3)
        self._render_layout(surface)

        # 3. 玩家显示 (5-4)
        self._render_player(surface)

        # 4. 敌人显示 (5-5)
        self._render_enemies(surface)

        # 5. 能量显示 (5-4)
        self._render_energy(surface)

        # 6. 手牌区占位 (后续阶段 6 实现)
        self._render_hand_area(surface)

        # 7. UI 组件
        for widget in self._widgets:
            if widget.visible:
                widget.render(surface)

        # 8-9: BOSS 阶段切换横幅
        if self._phase_banner_text and self._phase_banner_timer > 0:
            self._render_phase_banner(surface)

    def _render_phase_banner(self, surface) -> None:
        """在战斗区上方绘制 BOSS 阶段切换横幅"""
        font = self._get_font_h3()
        if not font:
            return
        text_surf = font.render(self._phase_banner_text, True, COLOR_GOLD)
        tw, th = text_surf.get_size()
        bw = tw + 40
        bh = th + 20
        bx = (SCREEN_WIDTH - bw) // 2
        by = _HEADER_H + 16

        # 背景（透明）
        bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        bg.fill((40, 20, 20, 220))
        surface.blit(bg, (bx, by))
        # 边框
        pygame.draw.rect(
            surface, COLOR_GOLD,
            pygame.Rect(bx, by, bw, bh),
            2, border_radius=6,
        )
        # 文字
        surface.blit(text_surf, (bx + 20, by + 10))

    # ── 5-3: 布局渲染 ────────────────────────────────────────────────────

    def _render_layout(self, surface) -> None:
        """绘制战斗场景的分区边界 (调试用, 可后续隐藏)"""
        # 顶部信息栏背景
        header_rect = pygame.Rect(0, 0, SCREEN_WIDTH, _HEADER_H)
        pygame.draw.rect(surface, (18, 18, 36), header_rect)
        pygame.draw.line(
            surface, COLOR_DIVIDER,
            (0, _HEADER_H), (SCREEN_WIDTH, _HEADER_H), 1
        )

        # 手牌区分隔线
        hand_y = SCREEN_HEIGHT - _HAND_AREA_H
        pygame.draw.line(
            surface, COLOR_DIVIDER,
            (0, hand_y), (SCREEN_WIDTH, hand_y), 1
        )

    # ── 5-4: 玩家渲染 ────────────────────────────────────────────────────

    def _render_player(self, surface) -> None:
        """渲染玩家: 占位图 + 血条 + 格挡"""
        if not self._world or not _esper_available:
            return
        if self._player_entity < 0:
            return

        try:
            pos = self._world.component_for_entity(self._player_entity, Position)
            sprite = self._world.component_for_entity(self._player_entity, Sprite)
            hp = self._world.component_for_entity(self._player_entity, Health)
            block = self._world.component_for_entity(self._player_entity, Block)
        except (KeyError, Exception):
            return

        cx, cy = int(pos.x), int(pos.y)

        # 角色占位矩形
        rect = pygame.Rect(
            cx - sprite.width // 2,
            cy - sprite.height // 2,
            sprite.width, sprite.height
        )
        pygame.draw.rect(surface, sprite.color, rect, border_radius=6)
        pygame.draw.rect(surface, (200, 200, 220), rect, 2, border_radius=6)

        # 角色名标签
        font = self._get_font_caption()
        if font:
            try:
                tag = self._world.component_for_entity(self._player_entity, PlayerTag)
                name_text = tag.character_id.capitalize()
            except (KeyError, Exception):
                name_text = "Player"
            name_surf = font.render(name_text, True, COLOR_WHITE)
            name_rect = name_surf.get_rect(centerx=cx, bottom=rect.top - 4)
            surface.blit(name_surf, name_rect)

        # 血条 (角色下方)
        bar_x = cx - _HP_BAR_W // 2
        bar_y = rect.bottom + 6
        self._draw_hp_bar(surface, bar_x, bar_y, _HP_BAR_W, _HP_BAR_H,
                          hp.current, hp.maximum)

        # HP 文字
        if font:
            hp_text = f"{hp.current}/{hp.maximum}"
            hp_surf = font.render(hp_text, True, COLOR_WHITE)
            hp_rect = hp_surf.get_rect(centerx=cx, top=bar_y + _HP_BAR_H + 2)
            surface.blit(hp_surf, hp_rect)

        # 格挡值
        if block.current > 0:
            self._draw_block_indicator(surface, cx, rect.top - 24, block.current)

        # 7-5: Buff 图标显示 (血条下方)
        try:
            buff_list = self._world.component_for_entity(self._player_entity, BuffList)
            buff_y = bar_y + _HP_BAR_H + 20
            self._draw_buff_icons(surface, cx, buff_y, buff_list)
        except (KeyError, Exception):
            pass

    def _render_energy(self, surface) -> None:
        """渲染能量球 (左下角)"""
        if not self._world or not _esper_available:
            return
        if self._player_entity < 0:
            return

        try:
            energy = self._world.component_for_entity(self._player_entity, Energy)
        except (KeyError, Exception):
            return

        # 能量球位置
        ex, ey = _ENERGY_X + 30, _ENERGY_Y + 20
        radius = 28

        # 外圈
        pygame.draw.circle(surface, (30, 50, 80), (ex, ey), radius)
        pygame.draw.circle(surface, (60, 120, 200), (ex, ey), radius, 2)

        # 数字
        font = self._get_font_h3()
        if font:
            energy_text = f"{energy.current}/{energy.maximum}"
            text_surf = font.render(energy_text, True, COLOR_WHITE)
            text_rect = text_surf.get_rect(center=(ex, ey))
            surface.blit(text_surf, text_rect)

        # 标签
        font_cap = self._get_font_caption()
        if font_cap:
            label_surf = font_cap.render("能量", True, COLOR_TEXT_SECONDARY)
            label_rect = label_surf.get_rect(centerx=ex, top=ey + radius + 4)
            surface.blit(label_surf, label_rect)

    # ── 5-5: 敌人渲染 ────────────────────────────────────────────────────

    def _render_enemies(self, surface) -> None:
        """渲染所有敌人: 占位图 + 血条 + 意图图标"""
        if not self._world or not _esper_available:
            return

        for eid in self._enemy_entities:
            try:
                self._render_single_enemy(surface, eid)
            except (KeyError, Exception):
                continue

    def _render_single_enemy(self, surface, eid: int) -> None:
        """渲染单个敌人"""
        pos = self._world.component_for_entity(eid, Position)
        sprite = self._world.component_for_entity(eid, Sprite)
        hp = self._world.component_for_entity(eid, Health)
        tag = self._world.component_for_entity(eid, EnemyTag)

        if not hp.is_alive:
            return

        cx, cy = int(pos.x), int(pos.y)

        # 判断是否是 BOSS
        is_boss = tag.enemy_type == "boss"

        # 敌人占位矩形
        rect = pygame.Rect(
            cx - sprite.width // 2,
            cy - sprite.height // 2,
            sprite.width, sprite.height
        )
        pygame.draw.rect(surface, sprite.color, rect, border_radius=4)

        # 边框: BOSS 金色, 精英橙色, 普通灰色
        if is_boss:
            border_color = COLOR_GOLD
            border_w = 3
        elif tag.enemy_type == "elite":
            border_color = (200, 120, 40)
            border_w = 2
        else:
            border_color = (100, 100, 110)
            border_w = 1
        pygame.draw.rect(surface, border_color, rect, border_w, border_radius=4)

        # 敌人名称
        font = self._get_font_caption()
        if font:
            name_surf = font.render(tag.name, True, COLOR_WHITE)
            name_rect = name_surf.get_rect(centerx=cx, bottom=rect.top - 4)
            surface.blit(name_surf, name_rect)

        # 血条
        bar_w = sprite.width if not is_boss else sprite.width + 20
        bar_h = _HP_BAR_H if not is_boss else 12
        bar_x = cx - bar_w // 2
        bar_y = rect.bottom + 6
        fg_color = _HP_BAR_BOSS if is_boss else _HP_BAR_FG
        self._draw_hp_bar(surface, bar_x, bar_y, bar_w, bar_h,
                          hp.current, hp.maximum, fg_color=fg_color)

        # HP 文字
        if font:
            hp_text = f"{hp.current}/{hp.maximum}"
            hp_surf = font.render(hp_text, True, COLOR_WHITE)
            hp_rect = hp_surf.get_rect(centerx=cx, top=bar_y + bar_h + 2)
            surface.blit(hp_surf, hp_rect)

        # 格挡
        try:
            block = self._world.component_for_entity(eid, Block)
            if block.current > 0:
                self._draw_block_indicator(surface, cx, rect.top - 24, block.current)
        except (KeyError, Exception):
            pass

        # 意图图标 (5-5)
        try:
            intent = self._world.component_for_entity(eid, IntentDisplay)
            self._draw_intent(surface, cx, rect.top - 44, intent)
        except (KeyError, Exception):
            pass

        # 7-5: Buff 图标显示 (HP文字下方)
        try:
            buff_list = self._world.component_for_entity(eid, BuffList)
            buff_y = bar_y + bar_h + 18
            self._draw_buff_icons(surface, cx, buff_y, buff_list)
        except (KeyError, Exception):
            pass

    # ── 手牌区占位 ───────────────────────────────────────────────────────

    def _render_hand_area(self, surface) -> None:
        """手牌区域占位渲染 (阶段 6 实现卡牌 UI)"""
        hand_y = SCREEN_HEIGHT - _HAND_AREA_H
        # 半透明背景
        hand_surf = pygame.Surface((SCREEN_WIDTH, _HAND_AREA_H), pygame.SRCALPHA)
        hand_surf.fill((15, 15, 30, 180))
        surface.blit(hand_surf, (0, hand_y))

        # 占位文字
        font = self._get_font_caption()
        if font:
            text = "[ 手牌区 - 阶段6实现 ]"
            text_surf = font.render(text, True, COLOR_TEXT_SECONDARY)
            text_rect = text_surf.get_rect(
                center=(SCREEN_WIDTH // 2, hand_y + _HAND_AREA_H // 2)
            )
            surface.blit(text_surf, text_rect)

    # ══════════════════════════════════════════════════════════════════════
    # 渲染辅助方法
    # ══════════════════════════════════════════════════════════════════════

    def _draw_hp_bar(self, surface, x: int, y: int, w: int, h: int,
                     current: int, maximum: int,
                     fg_color: Tuple[int, int, int] = None) -> None:
        """
        绘制血条。
        HP < 30% 时变为红色。
        """
        ratio = current / max(1, maximum)

        # 背景
        bg_rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surface, _HP_BAR_BG, bg_rect, border_radius=2)

        # 前景
        if fg_color is None:
            fg_color = _HP_BAR_DANGER if ratio < 0.3 else _HP_BAR_FG
        fg_w = max(0, int(w * ratio))
        if fg_w > 0:
            fg_rect = pygame.Rect(x, y, fg_w, h)
            pygame.draw.rect(surface, fg_color, fg_rect, border_radius=2)

        # 边框
        pygame.draw.rect(surface, (80, 80, 80), bg_rect, 1, border_radius=2)

    def _draw_block_indicator(self, surface, cx: int, y: int,
                              amount: int) -> None:
        """绘制格挡值指示器 (盾牌图标 + 数字)"""
        # 盾形背景
        shield_size = 18
        points = [
            (cx, y - shield_size),
            (cx - shield_size // 2, y - shield_size + 4),
            (cx - shield_size // 2, y - 4),
            (cx, y),
            (cx + shield_size // 2, y - 4),
            (cx + shield_size // 2, y - shield_size + 4),
        ]
        pygame.draw.polygon(surface, _BLOCK_COLOR, points)
        pygame.draw.polygon(surface, (120, 180, 240), points, 1)

        # 数字
        font = self._get_font_caption()
        if font:
            text_surf = font.render(str(amount), True, COLOR_WHITE)
            text_rect = text_surf.get_rect(center=(cx, y - shield_size // 2))
            surface.blit(text_surf, text_rect)

    def _draw_intent(self, surface, cx: int, y: int,
                     intent: IntentDisplay) -> None:
        """绘制敌人意图图标"""
        # 图标颜色
        color = _INTENT_COLORS.get(intent.intent_type, (120, 120, 120))

        # 圆形背景
        radius = 12
        pygame.draw.circle(surface, (30, 30, 40), (cx, y), radius)
        pygame.draw.circle(surface, color, (cx, y), radius, 2)

        # 意图符号
        font = self._get_font_caption()
        if font:
            symbols = {
                "attack": "⚔",
                "defend": "🛡",
                "buff": "↑",
                "debuff": "↓",
                "unknown": "?",
            }
            symbol = symbols.get(intent.intent_type, "?")
            sym_surf = font.render(symbol, True, color)
            sym_rect = sym_surf.get_rect(center=(cx, y))
            surface.blit(sym_surf, sym_rect)

        # 数值 (如果有)
        if intent.intent_value > 0:
            val_surf = font.render(str(intent.intent_value), True, color)
            val_rect = val_surf.get_rect(centerx=cx, top=y + radius + 2)
            surface.blit(val_surf, val_rect)

    # ── 7-5: Buff UI 显示 ────────────────────────────────────────────────

    def _draw_buff_icons(self, surface, cx: int, y: int,
                         buff_list: BuffList) -> None:
        """
        在实体血条下方绘制 buff 图标和层数 (7-5)。
        - 小图标 + 数字形式显示
        - 鼠标悬停时显示 tooltip（名称+说明）
        - buff 移除时图标消失（由 BuffList 数据驱动）
        """
        from src.systems.buff_system import get_buff_info, get_buff_tooltip

        if not buff_list.buffs:
            return

        icon_size = 18
        icon_gap = 4
        total_width = len(buff_list.buffs) * (icon_size + icon_gap) - icon_gap
        start_x = cx - total_width // 2

        font = self._get_font_caption()
        mouse_pos = pygame.mouse.get_pos() if _pygame_available else (0, 0)

        for i, buff in enumerate(buff_list.buffs):
            ix = start_x + i * (icon_size + icon_gap)
            iy = y

            info = get_buff_info(buff.buff_type)
            color = info.get("color", (120, 120, 120))
            is_debuff = info.get("is_debuff", False)

            # 图标背景 (圆角小方块)
            icon_rect = pygame.Rect(ix, iy, icon_size, icon_size)
            bg_color = (40, 20, 20) if is_debuff else (20, 30, 40)
            pygame.draw.rect(surface, bg_color, icon_rect, border_radius=3)
            pygame.draw.rect(surface, color, icon_rect, 1, border_radius=3)

            # 层数/持续时间数字
            if font:
                display_val = buff.stacks if buff.stacks > 1 else ""
                if buff.duration > 0 and buff.stacks <= 1:
                    display_val = buff.duration
                if display_val:
                    num_surf = font.render(str(display_val), True, COLOR_WHITE)
                    num_rect = num_surf.get_rect(center=icon_rect.center)
                    surface.blit(num_surf, num_rect)
                else:
                    # 单层时显示一个小色点
                    dot_cx = icon_rect.centerx
                    dot_cy = icon_rect.centery
                    pygame.draw.circle(surface, color, (dot_cx, dot_cy), 4)

            # Tooltip: 鼠标悬停时显示
            if icon_rect.collidepoint(mouse_pos):
                tooltip_text = get_buff_tooltip(
                    buff.buff_type, buff.stacks, buff.duration
                )
                self._draw_tooltip(surface, mouse_pos[0], mouse_pos[1],
                                   tooltip_text)

    def _draw_tooltip(self, surface, mx: int, my: int, text: str) -> None:
        """绘制 tooltip 弹出提示"""
        font = self._get_font_caption()
        if not font:
            return

        # 计算文字尺寸
        text_surf = font.render(text, True, COLOR_WHITE)
        tw, th = text_surf.get_size()

        # 背景矩形
        padding = 6
        tip_w = tw + padding * 2
        tip_h = th + padding * 2

        # 位置 (在鼠标上方)
        tip_x = mx - tip_w // 2
        tip_y = my - tip_h - 8

        # 确保不超出屏幕
        tip_x = max(4, min(tip_x, SCREEN_WIDTH - tip_w - 4))
        tip_y = max(4, tip_y)

        # 绘制背景
        tip_rect = pygame.Rect(tip_x, tip_y, tip_w, tip_h)
        pygame.draw.rect(surface, (20, 20, 30), tip_rect, border_radius=4)
        pygame.draw.rect(surface, (100, 100, 120), tip_rect, 1, border_radius=4)

        # 绘制文字
        surface.blit(text_surf, (tip_x + padding, tip_y + padding))
