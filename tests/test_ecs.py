"""
ECS 组件和实体工厂单元测试
对应开发计划: 5-1 ECS 组件定义, 5-2 实体工厂
"""
import pytest

try:
    import esper
    _esper_available = True
except ImportError:
    _esper_available = False

from src.ecs.components import (
    Position, Sprite, Health, Stats, Block, Energy,
    Combat, BuffList, BuffInstance,
    PlayerTag, EnemyTag,
    AIController, IntentDisplay,
    BossController, BossPhaseData,
    SkillSet, SkillSlot, DropTable,
    CardHolder, RelicHolder, Wallet,
)
from src.ecs.entities import EntityFactory, create_player, create_enemy, create_boss


# ── 测试配置数据 ──────────────────────────────────────────────────────────

KNIGHT_CONFIG = {
    "id": "knight",
    "name": "骑士",
    "role": "warrior",
    "base_stats": {
        "health": 80,
        "attack": 12,
        "defense": 8,
        "speed": 5,
        "crit_rate": 0.05,
        "dodge_rate": 0.0,
    },
    "starting_gold": 100,
    "starting_relic": "rusted_shield",
    "starting_deck": ["strike", "strike", "defend", "defend"],
}

SKELETON_CONFIG = {
    "id": "skeleton_warrior",
    "name": "骷髅战士",
    "type": "common",
    "base_stats": {
        "health": 30,
        "attack": 8,
        "defense": 2,
        "speed": 4,
    },
    "ai_pattern": "melee_aggressive",
    "drop_table": {
        "gold_min": 5,
        "gold_max": 12,
        "relic_drop_chance": 0.05,
    },
}

ELITE_CONFIG = {
    "id": "death_knight",
    "name": "死亡骑士",
    "type": "elite",
    "base_stats": {
        "health": 200,
        "attack": 20,
        "defense": 15,
        "speed": 5,
    },
    "ai_pattern": "elite_melee",
    "special_skills": [
        {"id": "shield_bash", "description": "格挡反击", "cooldown": 5.0},
        {"id": "war_cry", "description": "提升攻击力", "cooldown": 8.0},
    ],
    "drop_table": {
        "gold_min": 30,
        "gold_max": 60,
        "relic_drop_chance": 1.0,
    },
}

BOSS_CONFIG = {
    "id": "bone_king",
    "name": "骸骨之王",
    "floor": 1,
    "base_stats": {
        "health": 500,
        "attack": 20,
        "defense": 10,
        "speed": 5,
    },
    "phases": [
        {"phase": 1, "hp_threshold": 1.0, "description": "基础攻击",
         "skills": [{"id": "bone_smash", "cooldown": 3.0}]},
        {"phase": 2, "hp_threshold": 0.7, "description": "召唤模式",
         "skills": [{"id": "summon_minions", "cooldown": 5.0}]},
        {"phase": 3, "hp_threshold": 0.3, "description": "狂暴模式",
         "skills": [{"id": "bone_rain", "cooldown": 2.0}]},
    ],
    "drop_table": {
        "gold_min": 100,
        "gold_max": 150,
        "essence": 3,
        "relic_choices": 3,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# 5-1: ECS 组件定义测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestPositionComponent:
    def test_default_values(self):
        pos = Position()
        assert pos.x == 0.0
        assert pos.y == 0.0

    def test_custom_values(self):
        pos = Position(x=100.5, y=200.3)
        assert pos.x == 100.5
        assert pos.y == 200.3


class TestSpriteComponent:
    def test_default_values(self):
        sprite = Sprite()
        assert sprite.sprite_key == ""
        assert sprite.width == 64
        assert sprite.height == 80
        assert sprite.visible is True

    def test_custom_values(self):
        sprite = Sprite(sprite_key="hero", width=48, height=64, color=(255, 0, 0))
        assert sprite.sprite_key == "hero"
        assert sprite.width == 48
        assert sprite.color == (255, 0, 0)


class TestHealthComponent:
    def test_default_values(self):
        hp = Health()
        assert hp.current == 100
        assert hp.maximum == 100
        assert hp.is_alive is True
        assert hp.ratio == 1.0

    def test_take_damage(self):
        hp = Health(current=50, maximum=100)
        actual = hp.take_damage(30)
        assert actual == 30
        assert hp.current == 20

    def test_take_lethal_damage(self):
        hp = Health(current=10, maximum=100)
        actual = hp.take_damage(50)
        assert actual == 10  # 只能扣到 0
        assert hp.current == 0
        assert hp.is_alive is False

    def test_heal(self):
        hp = Health(current=50, maximum=100)
        actual = hp.heal(30)
        assert actual == 30
        assert hp.current == 80

    def test_heal_capped(self):
        hp = Health(current=90, maximum=100)
        actual = hp.heal(50)
        assert actual == 10
        assert hp.current == 100

    def test_ratio(self):
        hp = Health(current=25, maximum=100)
        assert hp.ratio == 0.25


class TestStatsComponent:
    def test_default_values(self):
        s = Stats()
        assert s.attack == 10
        assert s.defense == 5
        assert s.speed == 5.0
        assert s.crit_rate == 0.05
        assert s.crit_multiplier == 1.5
        assert s.dodge_rate == 0.0

    def test_custom_values(self):
        s = Stats(attack=20, defense=10, crit_rate=0.3, dodge_rate=0.15)
        assert s.attack == 20
        assert s.crit_rate == 0.3
        assert s.dodge_rate == 0.15


class TestBlockComponent:
    def test_default(self):
        b = Block()
        assert b.current == 0

    def test_add_block(self):
        b = Block()
        b.add_block(15)
        assert b.current == 15
        b.add_block(5)
        assert b.current == 20

    def test_absorb_damage_partial(self):
        b = Block(current=10)
        remaining = b.absorb_damage(15)
        assert remaining == 5
        assert b.current == 0

    def test_absorb_damage_full(self):
        b = Block(current=20)
        remaining = b.absorb_damage(10)
        assert remaining == 0
        assert b.current == 10

    def test_reset(self):
        b = Block(current=15)
        b.reset()
        assert b.current == 0


class TestEnergyComponent:
    def test_default(self):
        e = Energy()
        assert e.current == 3
        assert e.maximum == 3

    def test_spend_success(self):
        e = Energy(current=3, maximum=3)
        assert e.spend(2) is True
        assert e.current == 1

    def test_spend_fail(self):
        e = Energy(current=1, maximum=3)
        assert e.spend(2) is False
        assert e.current == 1  # 不变

    def test_restore_full(self):
        e = Energy(current=0, maximum=3)
        e.restore_full()
        assert e.current == 3


class TestBuffListComponent:
    def test_add_buff(self):
        bl = BuffList()
        bl.add_buff("burning", stacks=2, duration=3)
        assert bl.has_buff("burning")
        assert bl.get_stacks("burning") == 2

    def test_stack_buff(self):
        bl = BuffList()
        bl.add_buff("poisoned", stacks=1)
        bl.add_buff("poisoned", stacks=2)
        assert bl.get_stacks("poisoned") == 3

    def test_remove_buff(self):
        bl = BuffList()
        bl.add_buff("frozen", stacks=1)
        bl.remove_buff("frozen")
        assert bl.has_buff("frozen") is False

    def test_get_stacks_missing(self):
        bl = BuffList()
        assert bl.get_stacks("nonexistent") == 0


class TestBossController:
    def test_phase_transition(self):
        ctrl = BossController(phases=[
            BossPhaseData(phase=1, hp_threshold=1.0),
            BossPhaseData(phase=2, hp_threshold=0.7),
            BossPhaseData(phase=3, hp_threshold=0.3),
        ], current_phase=1)

        assert ctrl.check_phase_transition(0.8) is False  # still phase 1
        assert ctrl.current_phase == 1

        assert ctrl.check_phase_transition(0.65) is True  # transition to 2
        assert ctrl.current_phase == 2

    def test_get_current_phase(self):
        ctrl = BossController(phases=[
            BossPhaseData(phase=1, hp_threshold=1.0, description="P1"),
            BossPhaseData(phase=2, hp_threshold=0.5, description="P2"),
        ], current_phase=1)
        pd = ctrl.get_current_phase_data()
        assert pd is not None
        assert pd.description == "P1"


class TestSkillSlot:
    def test_ready_by_default(self):
        sk = SkillSlot(skill_id="fireball", cooldown=3.0)
        assert sk.is_ready is True

    def test_use_and_tick(self):
        sk = SkillSlot(skill_id="fireball", cooldown=3.0)
        sk.use()
        assert sk.is_ready is False
        assert sk.current_cooldown == 3.0
        sk.tick(2.0)
        assert sk.is_ready is False
        sk.tick(1.5)
        assert sk.is_ready is True


# ═══════════════════════════════════════════════════════════════════════════════
# 5-2: 实体工厂测试
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _esper_available, reason="esper not installed")
class TestEntityFactory:
    def _make_world(self):
        return esper.World()

    def test_create_player_basic(self):
        """create_player 创建带完整组件的玩家实体"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_player(KNIGHT_CONFIG, x=200, y=400)

        assert eid >= 0
        # 验证核心组件存在
        assert world.has_component(eid, PlayerTag)
        assert world.has_component(eid, Position)
        assert world.has_component(eid, Health)
        assert world.has_component(eid, Stats)
        assert world.has_component(eid, Sprite)
        assert world.has_component(eid, Block)
        assert world.has_component(eid, Energy)
        assert world.has_component(eid, BuffList)
        assert world.has_component(eid, CardHolder)
        assert world.has_component(eid, RelicHolder)
        assert world.has_component(eid, Wallet)

    def test_create_player_stats(self):
        """玩家属性从配置正确读取"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_player(KNIGHT_CONFIG)

        hp = world.component_for_entity(eid, Health)
        assert hp.current == 80
        assert hp.maximum == 80

        stats = world.component_for_entity(eid, Stats)
        assert stats.attack == 12
        assert stats.defense == 8
        assert stats.speed == 5.0

        pos = world.component_for_entity(eid, Position)
        assert pos.x == 200.0

    def test_create_player_starting_deck(self):
        """玩家起始卡组正确加载"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_player(KNIGHT_CONFIG)

        cards = world.component_for_entity(eid, CardHolder)
        assert cards.deck == ["strike", "strike", "defend", "defend"]

    def test_create_player_starting_relic(self):
        """玩家起始遗物正确加载"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_player(KNIGHT_CONFIG)

        relics = world.component_for_entity(eid, RelicHolder)
        assert "rusted_shield" in relics.relic_ids

    def test_create_player_tag(self):
        """PlayerTag 正确记录角色 ID"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_player(KNIGHT_CONFIG)

        tag = world.component_for_entity(eid, PlayerTag)
        assert tag.character_id == "knight"

    def test_create_enemy_basic(self):
        """create_enemy 创建带完整组件的敌人实体"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_enemy(SKELETON_CONFIG, x=600, y=300)

        assert world.has_component(eid, EnemyTag)
        assert world.has_component(eid, Position)
        assert world.has_component(eid, Health)
        assert world.has_component(eid, Stats)
        assert world.has_component(eid, Sprite)
        assert world.has_component(eid, Block)
        assert world.has_component(eid, AIController)
        assert world.has_component(eid, IntentDisplay)
        assert world.has_component(eid, BuffList)
        assert world.has_component(eid, DropTable)

    def test_create_enemy_stats(self):
        """敌人属性从配置正确读取"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_enemy(SKELETON_CONFIG)

        hp = world.component_for_entity(eid, Health)
        assert hp.current == 30
        assert hp.maximum == 30

        stats = world.component_for_entity(eid, Stats)
        assert stats.attack == 8
        assert stats.defense == 2

        tag = world.component_for_entity(eid, EnemyTag)
        assert tag.enemy_id == "skeleton_warrior"
        assert tag.enemy_type == "common"
        assert tag.name == "骷髅战士"

    def test_create_elite_with_skills(self):
        """精英敌人附带技能组件"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_enemy(ELITE_CONFIG)

        assert world.has_component(eid, SkillSet)
        skills = world.component_for_entity(eid, SkillSet)
        assert len(skills.skills) == 2
        assert skills.skills[0].skill_id == "shield_bash"
        assert skills.skills[1].cooldown == 8.0

    def test_create_boss(self):
        """create_boss 创建带阶段控制器的 BOSS 实体"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_boss(BOSS_CONFIG)

        assert world.has_component(eid, EnemyTag)
        assert world.has_component(eid, BossController)
        assert world.has_component(eid, SkillSet)
        assert world.has_component(eid, DropTable)

        tag = world.component_for_entity(eid, EnemyTag)
        assert tag.enemy_type == "boss"
        assert tag.name == "骸骨之王"

        boss_ctrl = world.component_for_entity(eid, BossController)
        assert len(boss_ctrl.phases) == 3
        assert boss_ctrl.current_phase == 1
        assert boss_ctrl.boss_name == "骸骨之王"

        hp = world.component_for_entity(eid, Health)
        assert hp.maximum == 500

    def test_create_boss_drop_table(self):
        """BOSS 掉落表正确"""
        world = self._make_world()
        factory = EntityFactory(world)
        eid = factory.create_boss(BOSS_CONFIG)

        drop = world.component_for_entity(eid, DropTable)
        assert drop.gold_min == 100
        assert drop.essence == 3
        assert drop.relic_choices == 3

    def test_module_level_create_player(self):
        """模块级 create_player 函数向后兼容"""
        world = self._make_world()
        eid = create_player(world, KNIGHT_CONFIG, 100, 200)
        assert world.has_component(eid, PlayerTag)
        assert world.has_component(eid, Health)

    def test_module_level_create_enemy(self):
        """模块级 create_enemy 函数向后兼容"""
        world = self._make_world()
        eid = create_enemy(world, SKELETON_CONFIG, 500, 300)
        assert world.has_component(eid, EnemyTag)
        assert world.has_component(eid, Health)
