"""
配置加载器 - 对应文档 §10.5.2
YAML配置文件的统一读取入口，带内存缓存
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any

try:
    import yaml
    _yaml_available = True
except ImportError:
    _yaml_available = False


class ConfigLoader:
    """
    加载并缓存所有 YAML 配置。
    策划修改 config/ 目录下的 YAML 无需改代码即可生效。
    对应文档 §10.5.1 YAML配置示例
    """

    def __init__(self, config_path: str = "config") -> None:
        self.config_path = Path(config_path)
        self._cache: Dict[str, Any] = {}

    def _load_yaml(self, path: Path) -> Any:
        if not _yaml_available:
            raise RuntimeError("PyYAML 未安装，请执行 pip install PyYAML")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_game_config(self) -> dict:
        if "game_config" not in self._cache:
            self._cache["game_config"] = self._load_yaml(
                self.config_path / "game_config.yaml"
            )
        return self._cache["game_config"]

    def load_relics(self) -> Dict[str, dict]:
        """加载所有遗物配置，返回 {relic_id: config} 字典"""
        if "relics" not in self._cache:
            relics: Dict[str, dict] = {}
            relic_dir = self.config_path / "relics"
            for file in relic_dir.glob("*.yaml"):
                data = self._load_yaml(file)
                for relic in data.get("relics", []):
                    relics[relic["id"]] = relic
            self._cache["relics"] = relics
        return self._cache["relics"]

    def load_character(self, char_id: str) -> dict:
        """加载单个角色配置"""
        key = f"char_{char_id}"
        if key not in self._cache:
            path = self.config_path / "characters" / f"{char_id}.yaml"
            self._cache[key] = self._load_yaml(path)["character"]
        return self._cache[key]

    def load_all_characters(self) -> Dict[str, dict]:
        """加载所有角色配置"""
        if "characters" not in self._cache:
            chars: Dict[str, dict] = {}
            char_dir = self.config_path / "characters"
            for file in char_dir.glob("*.yaml"):
                data = self._load_yaml(file)["character"]
                chars[data["id"]] = data
            self._cache["characters"] = chars
        return self._cache["characters"]

    def load_all_enemies(self) -> Dict[str, dict]:
        """加载所有敌人配置"""
        if "enemies" not in self._cache:
            enemies: Dict[str, dict] = {}
            enemy_dir = self.config_path / "enemies"
            for file in enemy_dir.glob("*.yaml"):
                data = self._load_yaml(file)
                for enemy in data.get("enemies", data.get("bosses", [])):
                    enemies[enemy["id"]] = enemy
            self._cache["enemies"] = enemies
        return self._cache["enemies"]

    def load_floor_config(self, floor_number: int) -> dict:
        """加载楼层配置"""
        key = f"floor_{floor_number}"
        if key not in self._cache:
            path = self.config_path / "levels" / f"floor_{floor_number}.yaml"
            self._cache[key] = self._load_yaml(path)["floor"]
        return self._cache[key]

    def load_events(self) -> list:
        """加载所有随机事件"""
        if "events" not in self._cache:
            path = self.config_path / "events" / "random_events.yaml"
            self._cache["events"] = self._load_yaml(path).get("events", [])
        return self._cache["events"]

    def clear_cache(self) -> None:
        self._cache.clear()
