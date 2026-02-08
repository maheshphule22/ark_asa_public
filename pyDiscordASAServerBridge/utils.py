import json
import os
from dataclasses import dataclass, field


def _strip_json_comments(text: str) -> str:
    result = []
    in_string = False
    is_escaped = False
    in_line_comment = False
    in_block_comment = False
    i = 0

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                result.append(ch)
            elif ch == "\r":
                result.append(ch)
            else:
                result.append(" ")
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                result.append(" ")
                result.append(" ")
                in_block_comment = False
                i += 2
                continue
            if ch in ("\n", "\r"):
                result.append(ch)
            else:
                result.append(" ")
            i += 1
            continue

        if in_string:
            result.append(ch)
            if is_escaped:
                is_escaped = False
            elif ch == "\\":
                is_escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            result.append(" ")
            result.append(" ")
            i += 2
            continue

        if ch == "/" and nxt == "*":
            in_block_comment = True
            result.append(" ")
            result.append(" ")
            i += 2
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def load_json_file_with_comments(filename: str):
    with open(filename, "r", encoding="utf-8") as config_file:
        raw_text = config_file.read()
    return json.loads(_strip_json_comments(raw_text))


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


def _parse_bool(value, default, label):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().casefold()
        if text in ("true", "1", "yes", "y", "on"):
            return True
        if text in ("false", "0", "no", "n", "off"):
            return False
    print(f"Invalid config for {label} : {value}; using default={default}")
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
class DiscordControlConfig:
    _role: str = ""
    _count: object = 1
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

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            return None
        return cls(
            data.get("role", ""),
            data.get("cmd_count", 1),
            data.get("success_cooldown"),
            data.get("failure_cooldown"),
            data.get("allowed_guild_ids"),
            data.get("allowed_channel_ids"),
        )


@dataclass
class DiscordCommadConfig:
    _name: str
    _description: str
    _role: str = ""
    _count: object = 1
    _success_cooldown: object = None
    _failure_cooldown: object = None
    _allowed_guild_ids: object = None
    _allowed_channel_ids: object = None
    _backend_req: object = None
    _response_processing: object = None
    _require_single_match: object = None
    _arguments: object = None
    _discord_controls: object = None

    _count_int: int = field(init=False, default=1)
    _success_cooldown_float: float = field(init=False, default=0.0)
    _failure_cooldown_float: float = field(init=False, default=0.0)
    _allowed_guild_ids_list: list[int] = field(init=False, default_factory=list)
    _allowed_channel_ids_list: list[int] = field(init=False, default_factory=list)
    _backend_req_list: list[dict] = field(init=False, default_factory=list)
    _response_processing_dict: dict = field(init=False, default_factory=dict)
    _require_single_match_bool: bool = field(init=False, default=True)
    _arguments_dict: dict = field(init=False, default_factory=dict)
    _controls_list: list[DiscordControlConfig] = field(init=False, default_factory=list)

    def __post_init__(self):
        self._count_int = _parse_int(self._count, 1, "_count")
        self._success_cooldown_float = _parse_float(self._success_cooldown, 0.0, "_success_cooldown")
        self._failure_cooldown_float = _parse_float(self._failure_cooldown, 0.0, "_failure_cooldown")
        self._allowed_guild_ids_list = _parse_id_list(self._allowed_guild_ids, "_allowed_guild_ids")
        self._allowed_channel_ids_list = _parse_id_list(self._allowed_channel_ids, "_allowed_channel_ids")
        if isinstance(self._backend_req, list):
            self._backend_req_list = [item for item in self._backend_req if isinstance(item, dict)]
        else:
            self._backend_req_list = []
        if isinstance(self._response_processing, dict):
            self._response_processing_dict = dict(self._response_processing)
        else:
            self._response_processing_dict = {}
        self._require_single_match_bool = _parse_bool(
            self._require_single_match,
            True,
            "_require_single_match",
        )
        if isinstance(self._arguments, dict):
            self._arguments_dict = dict(self._arguments)
        else:
            self._arguments_dict = {}

        self._controls_list = []
        if isinstance(self._discord_controls, list):
            for control_data in self._discord_controls:
                control = DiscordControlConfig.from_dict(control_data)
                if control is not None:
                    self._controls_list.append(control)

        if not self._controls_list:
            self._controls_list.append(
                DiscordControlConfig(
                    self._role,
                    self._count,
                    self._success_cooldown,
                    self._failure_cooldown,
                    self._allowed_guild_ids,
                    self._allowed_channel_ids,
                )
            )

        # Keep legacy fields mapped to first control for backward compatibility.
        primary = self._controls_list[0]
        self._role = primary._role
        self._count_int = primary._count_int
        self._success_cooldown_float = primary._success_cooldown_float
        self._failure_cooldown_float = primary._failure_cooldown_float
        self._allowed_guild_ids_list = primary._allowed_guild_ids_list
        self._allowed_channel_ids_list = primary._allowed_channel_ids_list

class CommandConfigs:
    def __init__(self):
        self.cmd_list = []
        configs = self.load_json_config()
        default_controls = configs.get("default_discord_controls", [])
        if not isinstance(default_controls, list):
            default_controls = []

        for command in configs.get("commands", []):
            if not isinstance(command, dict):
                continue

            has_legacy_controls = any(
                key in command
                for key in (
                    "role",
                    "cmd_count",
                    "success_cooldown",
                    "failure_cooldown",
                    "allowed_guild_ids",
                    "allowed_channel_ids",
                )
            )

            command_controls = command.get("discord_controls")
            if isinstance(command_controls, list):
                discord_controls = command_controls
            elif "discord_controls" in command and has_legacy_controls:
                discord_controls = None
            elif "discord_controls" in command:
                discord_controls = default_controls
            elif has_legacy_controls:
                discord_controls = None
            else:
                discord_controls = default_controls

            cmd1_config = DiscordCommadConfig(
                command.get("name", ""),
                command.get("description", ""),
                command.get("role", ""),
                command.get("cmd_count", 1),
                command.get("success_cooldown"),
                command.get("failure_cooldown"),
                command.get("allowed_guild_ids"),
                command.get("allowed_channel_ids"),
                command.get("backend_req"),
                command.get("response_processing"),
                command.get("require_single_match"),
                command.get("arguments"),
                discord_controls,
            )
            self.cmd_list.append(cmd1_config)
            
    def get_config_at(self, index:int=0):
        return self.cmd_list[index] if len(self.cmd_list) > index else None

    def load_json_config(self, filename='DASAB_CFG_CMD.json'):
        """Loads a JSON configuration file and returns a dictionary."""
        # Ensure the file exists before trying to open it
        if not os.path.exists(filename):
            print(f"Error: Configuration file '{filename}' not found.")
            return {"commands": []}
        try:
            data = load_json_file_with_comments(filename)
            if not isinstance(data, dict):
                print(f"Error: Configuration file '{filename}' is not a JSON object.")
                return {"commands": []}
            if "commands" not in data or not isinstance(data["commands"], list):
                data["commands"] = []
            if "default_discord_controls" not in data or not isinstance(data["default_discord_controls"], list):
                data["default_discord_controls"] = []
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

    def get_command_key(self, config, fallback_name: str, control=None) -> str:
        if config is not None and getattr(config, "_name", ""):
            base_key = config._name
        else:
            base_key = fallback_name
        if control is None:
            return base_key
        role_key = str(getattr(control, "_role", "") or "").strip().casefold()
        if role_key:
            return f"{base_key}:{role_key}"
        return base_key

    def get_cooldown_seconds(self, config, success: bool, control=None) -> float:
        source = control if control is not None else config
        if source is None:
            return 0.0
        seconds = source._success_cooldown_float if success else source._failure_cooldown_float
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
