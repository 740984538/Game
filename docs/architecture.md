# 深渊回响：无尽轮回 — 架构说明文档

## 1. 项目概述

| 项目 | 说明 |
|------|------|
| 游戏名称 | 深渊回响：无尽轮回 |
| 类型 | 单机 Roguelike + ARPG |
| 开发语言 | Python 3.11+ |
| 游戏引擎 | Pygame 2.5+ |
| 架构模式 | ECS（Entity-Component-System）|
| ECS 实现库 | Esper 3.0+ |
| 数据存储 | SQLite（通过 Python 标准库 sqlite3）|
| 配置格式 | YAML（PyYAML）|
| 随机生成 | 确定性 RNG（Python random.Random + NumPy）|

---

## 2. 目录结构总览

```
├── main.py                  # 游戏入口
├── requirements.txt         # 依赖清单
├── setup.py                 # 打包配置
├── .gitignore
│
├── config/                  # 策划数据表（YAML，无需改代码）
├── src/                     # 全部源代码
│   ├── core/                # 核心框架（主循环、状态机、事件总线、资源管理）
│   ├── ecs/                 # ECS 层（组件定义、实体工厂、处理器注册）
│   ├── systems/             # 游戏系统（每个 Processor 独立文件）
│   ├── generation/          # 程序化生成（种子、地图、房间、战利品）
│   ├── entities/            # 游戏对象业务逻辑
│   ├── scenes/              # 游戏场景（每个 GameState 对应一个 Scene）
│   ├── ui/                  # UI 组件库
│   ├── data/                # 数据持久化（配置加载、数据库、存档）
│   └── utils/               # 通用工具（常量、枚举、辅助函数、日志）
│
├── assets/                  # 美术资源（图片、音频、字体）
├── saves/                   # 运行时存档（gitignore）
├── tests/                   # 自动化测试（pytest）
└── docs/                    # 文档
```

---

## 3. 核心架构：ECS

本项目采用 **Entity-Component-System** 架构（基于 `esper` 库），将数据与逻辑彻底分离。

### 3.1 三个核心概念

| 概念 | 说明 | 对应文件 |
|------|------|----------|
| **Entity（实体）** | 只是一个整数 ID，本身不含任何数据或逻辑 | `src/ecs/entities.py` |
| **Component（组件）** | 纯数据 dataclass，不含任何业务逻辑 | `src/ecs/components.py` |
| **System/Processor（系统）** | 处理拥有特定组件组合的实体的逻辑 | `src/systems/*.py` |

### 3.2 组件一览

```
Position      — 坐标 (x, y)
Velocity      — 速度向量 (vx, vy)
Collider      — 碰撞体 (AABB)
Health        — 生命值 (current / maximum)
Combat        — 战斗属性 (attack / defense / crit_rate / dodge_rate)
BuffList      — 持有的 Buff/Debuff 列表
Wallet        — 金币与精华数量
Renderable    — 渲染信息 (sprite_key / layer / visible)
Animation     — 动画状态
PlayerTag     — 标记该实体为玩家（零数据标签）
EnemyTag      — 标记该实体为敌人（含 enemy_id / type）
SummonTag     — 标记该实体为召唤物
AIController  — 敌人AI状态 (ai_pattern / state / target)
CardHolder    — 卡牌手牌/牌库/弃牌堆 + 能量
RelicHolder   — 持有遗物ID列表
```

### 3.3 处理器执行顺序（优先级）

```
优先级 10  → InputProcessor      键盘/手柄输入 → 修改 Velocity
优先级 20  → AIProcessor         敌人行为决策 → 修改 Velocity / 触发攻击
优先级 30  → MovementProcessor   坐标更新 + 边界约束
优先级 40  → CombatProcessor     碰撞检测 + 伤害结算 + 发布事件
优先级 50  → BuffProcessor       Buff 计时衰减 + tick 效果（燃烧等）
优先级 60  → RelicProcessor      遗物事件监听（通过 EventManager）
优先级 70  → LootProcessor       死亡掉落生成
优先级 80  → EconomyProcessor    货币上限约束
优先级 90  → RenderProcessor     按层级排序渲染
优先级 100 → UIProcessor         HUD 数据刷新
优先级 110 → AudioProcessor      音效触发
```

---

## 4. 状态机

游戏状态由 `StateMachine`（`src/core/state_machine.py`）统一管理，每个 `GameState` 枚举值对应一个 `BaseScene` 子类。

```
GameState 枚举              对应 Scene 类
─────────────────────────────────────────────────────
MAIN_MENU            →  MainMenuScene
CHARACTER_SELECT     →  CharacterSelectScene
MAP_NAVIGATION       →  MapNavigationScene
COMBAT               →  CombatScene           ← ECS 世界在此运行
SHOP                 →  ShopScene
EVENT                →  EventScene
REST                 →  RestScene
RELIC_SELECT         →  RelicSelectScene
PAUSE                →  PauseScene
GAME_OVER            →  GameOverScene
VICTORY              →  VictoryScene
```

**场景生命周期：**
```
StateMachine.change(new_state)
    → old_scene.exit()
    → new_scene.enter(**kwargs)
    → 每帧：new_scene.update(dt)
    → 每帧：new_scene.render(surface)
```

---

## 5. 事件总线

`EventManager`（`src/core/event_manager.py`）是一个发布/订阅总线，用于解耦各系统。

**典型事件流：**
```
CombatProcessor 计算命中
    → event_manager.publish("on_hit", attacker=..., target=..., damage=100)
        → RelicManager.trigger("on_hit", ctx)   ← 遗物效果（如吸血）
        → AudioProcessor 订阅 → 播放命中音效
        → UIProcessor 订阅 → 显示伤害数字
```

**内置事件名称规范：**

| 事件名 | 触发时机 |
|--------|----------|
| `on_hit` | 攻击命中敌人 |
| `on_crit` | 暴击触发 |
| `on_kill` | 击杀敌人 |
| `on_damaged` | 玩家受到伤害 |
| `on_death` | 实体死亡 |
| `on_block` | 格挡成功 |
| `on_floor_start` | 进入新楼层 |
| `on_floor_end` | 完成当前楼层 |
| `on_relic_picked` | 拾取遗物 |
| `on_shop_open` | 开启商店 |

---

## 6. 配置系统

所有数值、内容数据均以 **YAML** 文件存储在 `config/` 目录，由 `ConfigLoader`（`src/data/config_loader.py`）统一加载，带内存缓存。

**策划修改流程：**
1. 编辑 `config/` 下对应 YAML 文件
2. 无需修改任何代码
3. 重启游戏即生效

**配置目录结构：**
```
config/
├── game_config.yaml         全局参数（分辨率、帧率、数值上限）
├── characters/              5个角色配置（骑士/刺客/法师/游侠/死灵）
├── relics/                  5类遗物配置（攻击/防御/功能/诅咒/传说）
├── enemies/                 3类敌人配置（普通/精英/BOSS）
├── cards/                   4类卡牌配置（攻击/技能/能力/诅咒）
├── levels/                  5层关卡配置（包含房间权重、敌人池）
└── events/                  随机事件配置
```

**遗物 YAML 格式：**
```yaml
relics:
  - id: fire_heart
    name: "火焰之心"
    rarity: epic               # common / rare / epic / legendary
    description: "火系伤害+50%"
    effects:
      - trigger: "on_deal_damage"
        effect_type: "damage_bonus"
        value: 0.5
        condition: "element == fire"
```

---

## 7. 地图生成系统

`MapGenerator`（`src/generation/map_generator.py`）使用确定性 RNG 生成楼层节点图。

**算法流程：**
```
1. 按 5 排生成节点，每排 2-4 个节点
2. 相邻排之间建立 1-2 条有向连接（向下）
3. 创建入口节点，连接第一排全部节点
4. 创建 BOSS 节点，第五排全部节点连向 BOSS
5. 按 room_weights 权重随机分配房间类型
```

**种子系统：**
```python
# 每日挑战：全球玩家相同种子
seed_manager.daily_seed()  → 基于 YYYYMMDD 生成

# 自定义模式：玩家输入种子
seed_manager.set_seed(123456)

# 普通模式：随机种子
seed_manager.new_seed()
```

---

## 8. 存档系统

存档使用 **pickle 序列化 + SQLite 持久化** 的方案。

```
GameSaveData
├── MetaProgress（元进度）    ← 实时保存，换局不清空
│   ├── soul_shards          灵魂碎片
│   ├── unlocked_characters  已解锁角色
│   ├── unlocked_relics      解锁入池的遗物
│   ├── achievements         已获得成就
│   └── seen_* (图鉴数据)
└── RunState（当局进度）      ← 仅普通难度以下可保存，死亡/通关后删除
    ├── seed                 本局种子
    ├── floor                当前层数
    ├── player               玩家快照（生命/金币/遗物/卡牌）
    └── map_state            已访问节点记录
```

**SQLite 表结构：**
```sql
meta_progress  (id, data BLOB, updated_at)
run_saves      (slot, data BLOB, updated_at)
settings       (key TEXT, value TEXT)
```

---

## 9. UI 层级

遵循文档 §6.1.1 的 6 层设计：

| Layer | 常量名 | 内容 |
|-------|--------|------|
| 0 | `LAYER_SCENE` | 战斗场景、特效渲染 |
| 1 | `LAYER_HUD` | 血条、能量、遗物栏、手牌 |
| 2 | `LAYER_FUNCTIONAL` | 遗物详情、地图全览、设置 |
| 3 | `LAYER_POPUP` | 遗物选择、事件选择、奖励展示 |
| 4 | `LAYER_TOOLTIP` | 浮动伤害数字、状态提示 |
| 5 | `LAYER_MENU` | 暂停菜单、主菜单、游戏结束界面 |

---

## 10. 开发流程

### 10.1 环境搭建

```bash
# 安装依赖
pip install -r requirements.txt

# 运行游戏
python main.py

# 运行测试
pytest tests/ -v

# 类型检查
mypy src/

# 代码格式化
black src/ tests/

# 打包为可执行文件
pyinstaller --onefile --windowed \
    --add-data "config;config" \
    --add-data "assets;assets" \
    --icon=assets/icon.ico \
    main.py
```

### 10.2 新增一个遗物

1. 在 `config/relics/` 对应 YAML 文件中添加遗物配置
2. 将遗物图片放入 `assets/images/relics/`
3. 不需要修改任何 Python 代码，重启游戏即可在随机池中出现

### 10.3 新增一个角色

1. 在 `config/characters/` 新建 `{char_id}.yaml`
2. 在 `assets/images/characters/` 添加对应精灵图
3. 不需要修改 Python 代码

### 10.4 新增一个 Buff 类型

1. 在 `src/utils/enums.py` 的 `BuffType` 枚举中添加
2. 在 `src/systems/buff_system.py` 的 `process()` 中添加 tick 处理逻辑
3. 在 `config/` 对应 YAML 中使用新 buff 名称

### 10.5 新增一个系统（Processor）

1. 在 `src/systems/` 创建新文件
2. 继承 `esper.Processor`，实现 `process(dt)` 方法
3. 在 `src/ecs/processors.py` 的 `register_all_processors()` 中注册，设置合适优先级

---

## 11. 代码规范

遵循文档 §10.6.1 规范：

| 规范 | 说明 |
|------|------|
| 代码风格 | PEP 8，使用 `black` 自动格式化 |
| 类型注解 | 所有函数参数和返回值必须有类型注解 |
| 文档字符串 | 公开类和函数必须有 docstring |
| 常量 | `UPPER_SNAKE_CASE`，统一放在 `src/utils/constants.py` |
| 类名 | `PascalCase` |
| 函数/变量 | `snake_case` |
| 枚举 | 统一放在 `src/utils/enums.py` |
| 第三方依赖 | 用 `try/except ImportError` 保护，确保 LSP 不报错导入失败 |

---

## 12. 文件索引

| 文件 | 职责 |
|------|------|
| `main.py` | 游戏入口，初始化 pygame 并启动 Game |
| `src/core/game.py` | 主循环，注册所有场景 |
| `src/core/state_machine.py` | 场景切换管理 |
| `src/core/event_manager.py` | 全局事件总线（发布/订阅）|
| `src/core/resource_manager.py` | 图片/音效/字体缓存管理 |
| `src/ecs/components.py` | 所有 ECS 组件定义 |
| `src/ecs/entities.py` | 实体工厂函数 |
| `src/ecs/processors.py` | 处理器注册与优先级 |
| `src/systems/combat_system.py` | 战斗逻辑（伤害/暴击/闪避）|
| `src/systems/movement_system.py` | 移动 + 边界约束 |
| `src/systems/relic_system.py` | 遗物事件触发 |
| `src/systems/buff_system.py` | Buff 计时与 tick 效果 |
| `src/generation/map_generator.py` | 楼层节点图生成 |
| `src/generation/loot_generator.py` | 加权随机战利品 |
| `src/generation/seed_manager.py` | 种子管理（每日挑战/自定义）|
| `src/data/config_loader.py` | YAML 配置加载（带缓存）|
| `src/data/save_manager.py` | 存档读写（pickle + SQLite）|
| `src/data/models.py` | 存档数据模型（MetaProgress / RunState）|
| `src/entities/relics/relic_manager.py` | 遗物业务逻辑 |
| `src/entities/player/build_manager.py` | Build 构筑管理 |
| `src/utils/constants.py` | 全局常量（颜色/尺寸/数值上限）|
| `src/utils/enums.py` | 全局枚举（GameState / Rarity 等）|
| `src/utils/helpers.py` | 数学/几何辅助函数 |
