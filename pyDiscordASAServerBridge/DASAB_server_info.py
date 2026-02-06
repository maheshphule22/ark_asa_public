DEFAULT_DISPLAY_TEMPLATE = "> {name} | {status} | {ip}:{port} | {map} | {players}/{maxPlayers} | Day:{day}"
DEFAULT_DISPLAY_FIELDS = {
    "name": "name",
    "status": "status",
    "ip": "ip",
    "port": "port",
    "map": "map",
    "players": "players",
    "maxPlayers": "maxPlayers",
    "day": "time_i",
}
from dataclasses import dataclass, field

_MISSING = object()


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return ""


class _ValueExtractor:
    @staticmethod
    def coerce_str(value):
        return "" if value is None else str(value)

    @staticmethod
    def collect_values(obj, target_keys, found=None):
        if found is None:
            found = {}
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in target_keys and key not in found and value is not None:
                    found[key] = value
                    if len(found) >= len(target_keys):
                        return found
                _ValueExtractor.collect_values(value, target_keys, found)
        elif isinstance(obj, list):
            for item in obj:
                _ValueExtractor.collect_values(item, target_keys, found)
                if len(found) >= len(target_keys):
                    return found
        return found


@dataclass(frozen=True, slots=True)
class DASAB_SERVER_CONFIG:
    server_id: str
    server_profile: str = ""
    server_name: str = ""
    server_ip: str = ""
    server_port: int | None = None
    server_manage_urls: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("Server config must be a dict.")
        server_id = str(
            data.get("server_id")
            or data.get("id")
            or data.get("battlemetrics_id")
            or ""
        ).strip()
        if not server_id:
            raise ValueError("Server config missing server_id.")

        server_profile = str(data.get("server_profile") or data.get("profile") or "").strip()
        server_name = str(data.get("server_name") or data.get("name") or "").strip()
        server_ip = str(data.get("server_ip") or data.get("ip") or "").strip()

        port_value = data.get("server_port") if "server_port" in data else data.get("port")
        server_port = None
        if port_value is not None and str(port_value).strip() != "":
            try:
                server_port = int(port_value)
            except Exception:
                server_port = None

        manage_urls = data.get("server_manage_urls") or data.get("manage_urls") or []
        if not isinstance(manage_urls, list):
            manage_urls = []
        manage_urls = [str(url).strip() for url in manage_urls if str(url).strip()]

        return cls(
            server_id=server_id,
            server_profile=server_profile,
            server_name=server_name,
            server_ip=server_ip,
            server_port=server_port,
            server_manage_urls=manage_urls,
        )


class DASAB_SERVER_INFO:
    __slots__ = (
        "id",
        "name",
        "status",
        "ip",
        "port",
        "map",
        "player",
        "maxPlayer",
        "days",
        "str_info",
        "config",
    )

    def __init__(
        self,
        server_id,
        data,
        display_template: str = DEFAULT_DISPLAY_TEMPLATE,
        display_fields: dict | None = None,
    ):
        root = data
        if isinstance(data, dict):
            data_obj = data.get("data")
            if isinstance(data_obj, dict):
                attributes = data_obj.get("attributes")
                if isinstance(attributes, dict):
                    root = attributes

        field_map = display_fields if isinstance(display_fields, dict) else DEFAULT_DISPLAY_FIELDS
        target_keys = set()
        for key in field_map.values():
            if isinstance(key, list):
                target_keys.update(key)
            else:
                target_keys.add(key)

        root_values = _ValueExtractor.collect_values(root, target_keys)
        data_values = (
            _ValueExtractor.collect_values(data, target_keys) if root is not data else root_values
        )
        values = _SafeFormatDict()

        for placeholder, key in field_map.items():
            value = _MISSING
            candidates = key if isinstance(key, list) else [key]
            for candidate in candidates:
                if candidate in root_values:
                    value = root_values[candidate]
                    break
                if candidate in data_values:
                    value = data_values[candidate]
                    break
            values[placeholder] = "" if value is _MISSING else value

        template = display_template or DEFAULT_DISPLAY_TEMPLATE
        self.str_info = template.format_map(values)

        self.id = server_id
        self.name = _ValueExtractor.coerce_str(values.get("name", ""))
        self.status = _ValueExtractor.coerce_str(values.get("status", ""))
        self.ip = _ValueExtractor.coerce_str(values.get("ip", ""))
        self.port = _ValueExtractor.coerce_str(values.get("port", ""))
        self.map = _ValueExtractor.coerce_str(values.get("map", ""))
        self.player = _ValueExtractor.coerce_str(values.get("players", ""))
        self.maxPlayer = _ValueExtractor.coerce_str(values.get("maxPlayers", ""))
        self.days = _ValueExtractor.coerce_str(values.get("day", ""))
        self.config = None
