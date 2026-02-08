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
from string import Formatter

_MISSING = object()


class _SafeFormatDict(dict):
    def __missing__(self, key):
        return ""


class _ValueExtractor:
    @staticmethod
    def coerce_str(value):
        return "" if value is None else str(value)

    @staticmethod
    def _normalize_segment(value):
        return str(value).strip().casefold()

    @staticmethod
    def _normalize_path(candidate):
        if candidate is None:
            return ""
        parts = [part for part in str(candidate).strip().split(".") if part.strip()]
        return ".".join(_ValueExtractor._normalize_segment(part) for part in parts)

    @staticmethod
    def build_index(obj, index=None, path=None):
        if index is None:
            index = {"by_key": {}, "by_path": {}}
        if path is None:
            path = []

        if isinstance(obj, dict):
            for key, value in obj.items():
                key_norm = _ValueExtractor._normalize_segment(key)
                current_path = [*path, key_norm]
                path_key = ".".join(current_path)
                if value is not None:
                    index["by_key"].setdefault(key_norm, value)
                    index["by_path"].setdefault(path_key, value)
                _ValueExtractor.build_index(value, index, current_path)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                current_path = [*path, str(idx)]
                path_key = ".".join(current_path)
                if item is not None:
                    index["by_path"].setdefault(path_key, item)
                _ValueExtractor.build_index(item, index, current_path)
        return index

    @staticmethod
    def _resolve_candidate(candidate, primary_index, secondary_index):
        if candidate is None:
            return _MISSING

        candidate_str = str(candidate).strip()
        if not candidate_str:
            return _MISSING

        normalized_key = _ValueExtractor._normalize_segment(candidate_str)
        normalized_path = _ValueExtractor._normalize_path(candidate_str)

        for index in (primary_index, secondary_index):
            if index is None:
                continue
            by_path = index.get("by_path", {})
            by_key = index.get("by_key", {})
            if normalized_path and normalized_path in by_path:
                value = by_path[normalized_path]
                if value is not None:
                    return value
            if normalized_key in by_key:
                value = by_key[normalized_key]
                if value is not None:
                    return value
        return _MISSING


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
        template = display_template or DEFAULT_DISPLAY_TEMPLATE
        root = data
        if isinstance(data, dict):
            data_obj = data.get("data")
            if isinstance(data_obj, dict):
                attributes = data_obj.get("attributes")
                if isinstance(attributes, dict):
                    root = attributes

        field_map = dict(display_fields) if isinstance(display_fields, dict) else dict(DEFAULT_DISPLAY_FIELDS)
        for _, field_name, _, _ in Formatter().parse(template):
            if field_name and field_name not in field_map:
                field_map[field_name] = field_name

        root_index = _ValueExtractor.build_index(root)
        data_index = _ValueExtractor.build_index(data) if root is not data else root_index
        values = _SafeFormatDict()

        for placeholder, key in field_map.items():
            candidates = list(key) if isinstance(key, list) else [key]
            if not any(str(candidate).strip() == placeholder for candidate in candidates):
                candidates.append(placeholder)
            value = _MISSING
            for candidate in candidates:
                value = _ValueExtractor._resolve_candidate(candidate, root_index, data_index)
                if value is not _MISSING:
                    break
            values[placeholder] = "" if value is _MISSING else value

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
