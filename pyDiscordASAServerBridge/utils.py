import json
import os
from dataclasses import dataclass, field


def _parse_int(value, default, label):
    if value is None or value == "":
        return default
    try:
        return int(value)
    except Exception as e:
        print(f"Invalid config for {label} : {value};\nError: {e}")
        return default


def _parse_float(value, default, label):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except Exception as e:
        print(f"Invalid config for {label} : {value};\nError: {e}")
        return default


def _parse_id_list(value, label):
    if value is None or value == "":
        return []
    items = []
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    else:
        items = [value]
    parsed = []
    for item in items:
        try:
            parsed.append(int(item))
        except Exception as e:
            print(f"Invalid config for {label} item : {item};\nError: {e}")
    return parsed


@dataclass
class DiscordCommadConfig:
    _name: str
    _description: str
    _role: str
    _count: object
    _success_cooldown: object = None
    _failure_cooldown: object = None
    _allowed_guild_ids: object = None
    _allowed_channel_ids: object = None

    _count_int: int = field(init=False, default=1)
    _success_cooldown_float: float = field(init=False, default=0.0)
    _failure_cooldown_float: float = field(init=False, default=0.0)
    _allowed_guild_ids_list: list[int] = field(init=False, default_factory=list)
    _allowed_channel_ids_list: list[int] = field(init=False, default_factory=list)

    def __post_init__(self):
        self._count_int = _parse_int(self._count, 1, "_count")
        self._success_cooldown_float = _parse_float(self._success_cooldown, 0.0, "_success_cooldown")
        self._failure_cooldown_float = _parse_float(self._failure_cooldown, 0.0, "_failure_cooldown")
        self._allowed_guild_ids_list = _parse_id_list(self._allowed_guild_ids, "_allowed_guild_ids")
        self._allowed_channel_ids_list = _parse_id_list(self._allowed_channel_ids, "_allowed_channel_ids")

class CommandConfigs:
    def __init__(self):
        self.cmd_list = []
        configs = self.load_json_config()
        for command in configs.get("commands", []):
            if not isinstance(command, dict):
                continue
            cmd1_config = DiscordCommadConfig(
                command.get("name", ""),
                command.get("description", ""),
                command.get("role", ""),
                command.get("cmd_count", 1),
                command.get("success_cooldown"),
                command.get("failure_cooldown"),
                command.get("allowed_guild_ids"),
                command.get("allowed_channel_ids"),
            )
            self.cmd_list.append(cmd1_config)
            
    def get_config_at(self, index:int=0):
        return self.cmd_list[index] if len(self.cmd_list) > index else None

    def load_json_config(self, filename='DisCmdConfig.json'):
        """Loads a JSON configuration file and returns a dictionary."""
        # Ensure the file exists before trying to open it
        if not os.path.exists(filename):
            print(f"Error: Configuration file '{filename}' not found.")
            return {"commands": []}
        try:
            with open(filename, 'r') as config_file:
                # json.load reads the file object and parses the JSON data
                data = json.load(config_file)
            if not isinstance(data, dict):
                print(f"Error: Configuration file '{filename}' is not a JSON object.")
                return {"commands": []}
            if "commands" not in data or not isinstance(data["commands"], list):
                data["commands"] = []
            return data
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from file '{filename}': {e}")
            return {"commands": []}
        except IOError as e:
            print(f"Error opening or reading file '{filename}': {e}")
            return {"commands": []}


class CooldownManager:
    def __init__(self):
        self._cooldown_until = {}

    def get_command_key(self, config, fallback_name: str) -> str:
        if config is not None and getattr(config, "_name", ""):
            return config._name
        return fallback_name

    def get_cooldown_seconds(self, config, success: bool) -> float:
        if config is None:
            return 0.0
        seconds = config._success_cooldown_float if success else config._failure_cooldown_float
        return seconds if seconds > 0 else 0.0

    def get_remaining(self, user_id: int, command_key: str, now: float) -> float:
        cooldown_until = self._cooldown_until.get((user_id, command_key), 0.0)
        remaining = cooldown_until - now
        return remaining if remaining > 0 else 0.0

    def set_cooldown(self, user_id: int, command_key: str, seconds: float, now: float) -> None:
        if seconds > 0:
            self._cooldown_until[(user_id, command_key)] = now + seconds
        else:
            self._cooldown_until.pop((user_id, command_key), None)
