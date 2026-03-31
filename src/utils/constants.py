"""
全局常量定义
对应文档 §6.3.1 色彩系统、§8.1.1 帧率要求、§6.3.2 字体规范
"""

# ── 显示 ──────────────────────────────────────────
SCREEN_WIDTH: int = 1280
SCREEN_HEIGHT: int = 720
FPS: int = 60
TITLE: str = "深渊回响：无尽轮回"

# ── 色彩系统（§6.3.1）────────────────────────────
COLOR_PRIMARY = (139, 69, 19)      # #8B4513 主色棕色
COLOR_DANGER = (220, 20, 60)       # #DC143C 深红-危险/伤害
COLOR_HEAL = (34, 139, 34)         # #228B22 森林绿-治疗/增益
COLOR_GOLD = (255, 215, 0)         # #FFD700 金色-传说品质
COLOR_EPIC = (147, 112, 219)       # #9370DB 紫色-史诗品质
COLOR_BG_DARK = (26, 26, 46)       # #1a1a2e 深背景
COLOR_BG_LIGHT = (22, 33, 62)      # #16213e 浅背景
COLOR_TEXT_PRIMARY = (233, 69, 96) # #e94560 主要文字
COLOR_TEXT_SECONDARY = (160, 160, 160)  # #a0a0a0 次要文字
COLOR_DIVIDER = (15, 52, 96)       # #0f3460 分割线
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)

# 稀有度颜色映射
RARITY_COLORS = {
    "common":    COLOR_WHITE,
    "rare":      (100, 149, 237),   # 矢车菊蓝
    "epic":      COLOR_EPIC,
    "legendary": COLOR_GOLD,
}

# ── 字体规范（§6.3.2）────────────────────────────
FONT_SIZE_H1: int = 36
FONT_SIZE_H2: int = 28
FONT_SIZE_H3: int = 20
FONT_SIZE_BODY: int = 16
FONT_SIZE_CAPTION: int = 14
FONT_SIZE_DAMAGE: int = 24

# ── 游戏数值上限（§3.1.2）────────────────────────
MAX_CRIT_RATE: float = 0.75
MAX_DODGE_RATE: float = 0.40
MAX_COOLDOWN_REDUCTION: float = 0.50
GOLD_CAP: int = 9999
ESSENCE_CAP: int = 99

# ── UI 层级（§6.1.1）─────────────────────────────
LAYER_SCENE: int = 0
LAYER_HUD: int = 1
LAYER_FUNCTIONAL: int = 2
LAYER_POPUP: int = 3
LAYER_TOOLTIP: int = 4
LAYER_MENU: int = 5

# ── 路径 ─────────────────────────────────────────
SAVE_DIR: str = "saves"
CONFIG_DIR: str = "config"
ASSETS_DIR: str = "assets"
