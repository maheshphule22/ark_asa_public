import asyncio
import json
import os
import time
import re

import requests
from dotenv import load_dotenv

from DASAB_server_info import (
    DASAB_SERVER_CONFIG,
    DASAB_SERVER_INFO,
    DEFAULT_DISPLAY_FIELDS,
    DEFAULT_DISPLAY_TEMPLATE,
)

SERVER_CONFIG_PATH = "DASAB_CFG_SERVERS.json"
ASA_MANAGER_TOKEN_ENV = "ASA_MANAGER_TOKEN"
DEFAULT_HTTP_TIMEOUT_SECONDS = 10
SERVER_PLACEHOLDER_NAMES = (
    "server_id",
    "server_profile",
    "server_name",
    "server_ip",
    "server_port",
)
BRACED_DOLLAR_PATTERN = re.compile(r"\{\$([A-Za-z_][A-Za-z0-9_]*)\}")
DOLLAR_BRACED_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
DOLLAR_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
BRACED_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
BACKEND_LOG_PATH = "DASAB_backend_requests.log"


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def _append_backend_log(line: str):
    try:
        with open(BACKEND_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass

class DASAB_SERVER_INFO_MANAGER:
    server_info_list = []
    def __init__(self):
        load_dotenv()
        self.server_configs, self.display_template, self.display_fields = self._load_server_configs(
            SERVER_CONFIG_PATH
        )
        self._config_by_id = {}
        self._config_by_profile = {}
        self._config_by_ip_port = {}
        self._index_server_configs()
        self._cache_ttl_seconds = 120
        self._cache = {"ts": 0.0, "data": "", "refreshing": False}

    def _load_server_configs(self, filename: str):
        if not os.path.exists(filename):
            print(f"Error: Server configuration file '{filename}' not found.")
            return [], DEFAULT_DISPLAY_TEMPLATE, DEFAULT_DISPLAY_FIELDS
        try:
            with open(filename, 'r') as config_file:
                data = json.load(config_file)
            if not isinstance(data, dict):
                print(f"Error: Server configuration file '{filename}' is not a JSON object.")
                return [], DEFAULT_DISPLAY_TEMPLATE, DEFAULT_DISPLAY_FIELDS
            servers = data.get("servers", [])
            if not isinstance(servers, list):
                print(f"Error: Server configuration file '{filename}' has invalid 'servers' list.")
                servers = []
            display_template = data.get("display_template", DEFAULT_DISPLAY_TEMPLATE)
            display_fields = data.get("display_fields", DEFAULT_DISPLAY_FIELDS)
            if not isinstance(display_fields, dict):
                display_fields = DEFAULT_DISPLAY_FIELDS
            configs = []
            for srv in servers:
                if not isinstance(srv, dict):
                    continue
                try:
                    configs.append(DASAB_SERVER_CONFIG.from_dict(srv))
                except Exception:
                    continue
            return configs, display_template, display_fields
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from file '{filename}': {e}")
            return [], DEFAULT_DISPLAY_TEMPLATE, DEFAULT_DISPLAY_FIELDS
        except IOError as e:
            print(f"Error opening or reading file '{filename}': {e}")
            return [], DEFAULT_DISPLAY_TEMPLATE, DEFAULT_DISPLAY_FIELDS

    def _extract_server_id(self, server_cfg):
        if isinstance(server_cfg, DASAB_SERVER_CONFIG):
            return server_cfg.server_id
        if isinstance(server_cfg, dict):
            return (
                server_cfg.get("server_id")
                or server_cfg.get("id")
                or server_cfg.get("battlemetrics_id")
                or ""
            )
        return ""

    def _normalize_id(self, value):
        return str(value).strip() if value is not None else ""

    def _normalize_profile(self, value):
        return str(value).strip().casefold() if value is not None else ""

    def _normalize_ip_port(self, ip, port):
        ip_val = str(ip).strip() if ip is not None else ""
        port_val = str(port).strip() if port is not None else ""
        if not ip_val or not port_val:
            return ""
        return f"{ip_val}:{port_val}"

    def _index_server_configs(self):
        self._config_by_id = {}
        self._config_by_profile = {}
        self._config_by_ip_port = {}
        for cfg in self.server_configs:
            if not isinstance(cfg, DASAB_SERVER_CONFIG):
                continue
            id_key = self._normalize_id(cfg.server_id)
            if id_key and id_key not in self._config_by_id:
                self._config_by_id[id_key] = cfg
            profile_key = self._normalize_profile(cfg.server_profile)
            if profile_key and profile_key not in self._config_by_profile:
                self._config_by_profile[profile_key] = cfg
            ip_port_key = self._normalize_ip_port(cfg.server_ip, cfg.server_port)
            if ip_port_key and ip_port_key not in self._config_by_ip_port:
                self._config_by_ip_port[ip_port_key] = cfg

    def _find_config_for_info(self, server_info: DASAB_SERVER_INFO):
        if server_info is None:
            return None
        id_key = self._normalize_id(server_info.id)
        if id_key and id_key in self._config_by_id:
            return self._config_by_id[id_key]
        if id_key:
            profile_key = self._normalize_profile(id_key)
            if profile_key and profile_key in self._config_by_profile:
                return self._config_by_profile[profile_key]
        profile_from_name = self._normalize_profile(server_info.name)
        if profile_from_name and profile_from_name in self._config_by_profile:
            return self._config_by_profile[profile_from_name]
        ip_port_key = self._normalize_ip_port(server_info.ip, server_info.port)
        if ip_port_key and ip_port_key in self._config_by_ip_port:
            return self._config_by_ip_port[ip_port_key]
        return None

    def _render_template(self, template: str, context: dict):
        if not template:
            return template

        def repl(match):
            key = match.group(1)
            value = context.get(key)
            return "" if value is None else str(value)

        result = BRACED_DOLLAR_PATTERN.sub(repl, template)
        result = DOLLAR_BRACED_PATTERN.sub(repl, result)
        result = DOLLAR_PATTERN.sub(repl, result)
        result = BRACED_PATTERN.sub(repl, result)
        return result

    def _try_parse_json(self, text: str):
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return None

    def _coerce_server_items(self, payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            if isinstance(payload.get("servers"), list):
                return payload.get("servers")
            if isinstance(payload.get("data"), list):
                return payload.get("data")
            if isinstance(payload.get("data"), dict):
                return [payload.get("data")]
        return []

    def _format_server_list_payload(self, payload, server_filter: str):
        items = self._coerce_server_items(payload)
        if not items:
            return None
        lines = []
        for item in items:
            if not isinstance(item, dict):
                continue
            server_id = item.get("id") or item.get("server_id") or ""
            info = DASAB_SERVER_INFO(
                server_id,
                item,
                self.display_template,
                self.display_fields,
            )
            if info.str_info:
                lines.append(info.str_info)
        if not lines:
            return None
        if server_filter:
            header = f"Success. Here is list of servers containing {server_filter} : \n"
        else:
            header = "Success. Here is full server list: \n"
        return header + "\n".join(lines) + "\nDone listing servers"

    def _parse_payload(self, payload_template: object, context: dict):
        if payload_template is None:
            return None
        if not isinstance(payload_template, str):
            return payload_template
        rendered = self._render_template(payload_template, context).strip()
        if rendered == "":
            return None
        if rendered.startswith("{") or rendered.startswith("["):
            try:
                return json.loads(rendered)
            except Exception:
                try:
                    return json.loads(rendered.replace("'", '"'))
                except Exception:
                    return rendered
        return rendered

    def _build_context(self, server_cfg: DASAB_SERVER_CONFIG, message: str | None = None):
        return {
            "server_id": server_cfg.server_id,
            "server_profile": server_cfg.server_profile,
            "server_name": server_cfg.server_name,
            "server_ip": server_cfg.server_ip,
            "server_port": server_cfg.server_port or "",
            "message": message or "",
        }

    def _req_needs_server(self, req: dict):
        end_pt = str(req.get("END_PT", ""))
        payload = str(req.get("Payload", ""))
        text = end_pt + " " + payload
        for name in SERVER_PLACEHOLDER_NAMES:
            if f"{{{name}}}" in text or f"${name}" in text or f"${{{name}}}" in text:
                return True
        return False

    def _iter_manage_urls(self, server_cfgs: list[DASAB_SERVER_CONFIG]):
        seen = set()
        urls = []
        for cfg in server_cfgs:
            for url in cfg.server_manage_urls:
                key = url.strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                urls.append(key)
        return urls

    def _call_backend(self, method: str, url: str, payload, auth: bool):
        headers = {}
        if auth:
            token = os.getenv(ASA_MANAGER_TOKEN_ENV, "").strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        try:
            _append_backend_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {method} {url} HEADERS {headers}")
            if payload is not None:
                _append_backend_log(f"PAYLOAD {payload}")
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS)
            else:
                if isinstance(payload, (dict, list)):
                    resp = requests.request(
                        method,
                        url,
                        headers=headers,
                        json=payload,
                        timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
                    )
                elif payload is not None:
                    resp = requests.request(
                        method,
                        url,
                        headers=headers,
                        data=str(payload),
                        timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
                    )
                else:
                    resp = requests.request(
                        method,
                        url,
                        headers=headers,
                        timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
                    )
            body_snippet = ""
            try:
                text = resp.text or ""
                body_snippet = text[:2000]
            except Exception:
                body_snippet = ""
            _append_backend_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {method} {url} -> {resp.status_code}")
            if body_snippet:
                _append_backend_log(body_snippet)
            return resp
        except Exception as e:
            _append_backend_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {method} {url} -> ERROR: {e}")
            return e

    def _request_backend_for_urls(
        self,
        req_cfg: dict,
        base_urls: list[str],
        context: dict,
        server_filter: str,
    ):
        method = str(req_cfg.get("type", "GET")).upper()
        end_pt = str(req_cfg.get("END_PT", "")).strip()
        auth = bool(req_cfg.get("Auth", False))
        payload = self._parse_payload(req_cfg.get("Payload"), context)

        if end_pt:
            end_pt = self._render_template(end_pt, context)

        if not base_urls:
            return False, "Failed. No server_manage_urls configured."

        for base_url in base_urls:
            url = base_url.rstrip("/")
            if end_pt:
                url = f"{url}/{end_pt.lstrip('/')}"
            resp = self._call_backend(method, url, payload, auth)
            if isinstance(resp, Exception):
                continue
            if 200 <= resp.status_code < 300:
                body = resp.text or ""
                parsed = self._try_parse_json(body)
                formatted = self._format_server_list_payload(parsed, server_filter) if parsed is not None else None
                if formatted:
                    return True, formatted
                if body:
                    return True, "Success.\n" + body
                return True, "Success."
        return False, f"Failed. {method} request failed for all configured URLs."

    def _match_server_configs(self, server_filter: str):
        if not server_filter:
            return list(self.server_configs)
        needle = server_filter.strip().casefold()
        matches = []
        for cfg in self.server_configs:
            if needle in cfg.server_id.casefold():
                matches.append(cfg)
                continue
            if cfg.server_profile and needle in cfg.server_profile.casefold():
                matches.append(cfg)
                continue
            if cfg.server_name and needle in cfg.server_name.casefold():
                matches.append(cfg)
                continue
            ip_port = f"{cfg.server_ip}:{cfg.server_port}" if cfg.server_ip and cfg.server_port else ""
            if ip_port and needle in ip_port.casefold():
                matches.append(cfg)
        return matches

    def execute_backend_req(
        self,
        server_filter: str,
        backend_req: list[dict],
        message: str | None = None,
    ):
        if not backend_req:
            return "Failed. No backend_req configured."

        matches = self._match_server_configs(server_filter)
        if not matches:
            return f"Failed. No server match for: {server_filter}"

        for req_cfg in backend_req:
            if self._req_needs_server(req_cfg):
                responses = []
                for cfg in matches:
                    context = self._build_context(cfg, message)
                    ok, response = self._request_backend_for_urls(
                        req_cfg,
                        cfg.server_manage_urls,
                        context,
                        server_filter,
                    )
                    if ok:
                        responses.append(response)
                    else:
                        responses.append(response)
                if responses:
                    success = any(resp.startswith("Success.") for resp in responses)
                    if success:
                        return "Success.\n" + "\n".join(responses)
            else:
                base_urls = self._iter_manage_urls(matches)
                context = self._build_context(matches[0], message) if matches else {}
                ok, response = self._request_backend_for_urls(
                    req_cfg,
                    base_urls,
                    context,
                    server_filter,
                )
                if ok:
                    return response

        return "Failed. All backend_req attempts failed."

    # TODO implement server listing locally instead of battlematrix for better performance
    def get_server_info(self, server_id = ""):
        url = f"https://api.battlemetrics.com/servers/{server_id}"
        try:
            response = requests.get(url)
            message = ""
            if response.status_code == 200:
                data = response.json()
                server = DASAB_SERVER_INFO(
                    server_id,
                    data,
                    self.display_template,
                    self.display_fields,
                )
                server.config = self._find_config_for_info(server)
                self.server_info_list.append(server)
                message += server.str_info
            else:
                message += f"Failed to retrieve data for server_id={server_id}" 
                print(f"Failed to retrieve data for server_id={server_id}, status_code = {response.status_code}") 
        except Exception as e:
            message += f"Error while receiving data for server_id={server_id}" 
            print(f"Error while receiving data for server_id={server_id}, {e}")
        return message
    
    def repopulate_all_server_list(self):
        self.server_info_list = [] # clearing old list
        server_info_str = ""
        for server_cfg in self.server_configs:
            server_id = self._extract_server_id(server_cfg)
            if not server_id:
                continue
            server_info_str += self.get_server_info(server_id) + "\n" # this also populates server_info_list
        return server_info_str
    
    def get_server_list(self, server_filter=""):
        info = self.get_only_server_list(server_filter)
        server_info = ""
        if (server_filter != ""):
            server_info = f"Success. Here is list of servers containing {server_filter} : \n" + info
        else:
            server_info = "Success. Here is full server list: \n" + info
        return server_info + "\nDone listing servers"
    
    def get_only_server_list(self, server_filter=""):
        server_info = self.repopulate_all_server_list()
        if (server_filter != ""):
            server_info = ""
            for server in self.server_info_list:
                if (server_filter.lower() in server.str_info.lower()):
                    server_info += server.str_info + "\n"
        return server_info

    def extract_server_names(self, server_info: str) -> list[str]:
        names = []
        seen = set()
        for line in server_info.splitlines():
            line = line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("success") or lowered.startswith("fail"):
                continue
            if line.startswith(">"):
                line = line[1:].strip()
            name = line.split(" | ", 1)[0].strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names

    def is_cache_stale(self, now: float | None = None) -> bool:
        if now is None:
            now = time.monotonic()
        return (now - self._cache["ts"]) > self._cache_ttl_seconds

    def is_cache_refreshing(self) -> bool:
        return self._cache["refreshing"]

    async def refresh_server_list_cache(self) -> None:
        if self._cache["refreshing"]:
            return
        self._cache["refreshing"] = True
        try:
            data = await asyncio.to_thread(self.get_only_server_list, "")
            self._cache["data"] = data or ""
            self._cache["ts"] = time.monotonic()
        finally:
            self._cache["refreshing"] = False

    async def get_autocomplete_names(self, current: str, limit: int = 25) -> list[str]:
        now = time.monotonic()
        if self.is_cache_stale(now) and not self.is_cache_refreshing():
            asyncio.create_task(self.refresh_server_list_cache())
        data = self.get_cached_only_server_list()
        if not data.strip():
            await self.refresh_server_list_cache()
            data = self.get_cached_only_server_list()
        if not data:
            return []
        current_lower = current.lower()
        names = []
        for name in self.extract_server_names(data):
            if current_lower in name.lower():
                names.append(name)
                if len(names) >= limit:
                    break
        return names

    async def run_cache_refresh_loop(self, interval_seconds: int = 180) -> None:
        while True:
            try:
                await self.refresh_server_list_cache()
            except Exception as e:
                print(f"Error refreshing server list cache: {e}")
            await asyncio.sleep(interval_seconds)

    def get_cached_only_server_list(self, server_filter=""):
        server_info = self._cache["data"] or ""
        if server_filter:
            lines = [
                line for line in server_info.splitlines()
                if server_filter.lower() in line.lower()
            ]
            return "\n".join(lines) + ("\n" if lines else "")
        return server_info

    def get_cached_server_list(self, server_filter=""):
        info = self.get_cached_only_server_list(server_filter)
        if not info.strip():
            target = server_filter if server_filter else "all servers"
            return f"Failed. No cached servers found for {target}."
        if server_filter:
            header = f"Success. Here is list of servers containing {server_filter} : \n"
        else:
            header = "Success. Here is full server list: \n"
        return header + info + "\nDone listing servers"

    async def get_cached_server_list_async(self, server_filter=""):
        if (self.is_cache_stale() and not self.is_cache_refreshing()) or not self.get_cached_only_server_list().strip():
            await self.refresh_server_list_cache()
        return self.get_cached_server_list(server_filter)
    
    # old function for reference
    # def request_server_start(self, server_filter=""):
    #     error_msg1 = f"Failed. \nPlease give name of server which will uniqly identify server from list, current input : {server_filter} : "
    #     if (server_filter == ""):
    #         return error_msg1
    #     server_info = self.get_only_server_list(server_filter)
    #     server_info_matches = server_info.strip().split('\n')
    #     if len(server_info_matches) == 1:
    #         for server in self.server_info_list:
    #             if server_info_matches[0].lower() == server.str_info.lower():  
    #                 if server.status.lower() == "online":
    #                     # TODO Requested Server is already online but do we still want to call start/restart?
    #                     return f"Failed. \nRequested Server is already online : \n{server.str_info}"
    #                 else:
    #                     # TODO call reserver startup from here we can use server.id or something here
    #                     return f"Success. \nRequesting Server startup : \n{server.str_info}"
    #     else:
    #         return error_msg1 + f" which gives {len(server_info_matches)} servers\n{"\n".join(server_info_matches)}" 
    
    def process_per_server_req(self, server_filter=""):
        error_msg1 = f"Failed. \nPlease give name of server which will uniqly identify server from list, current input : {server_filter} : "
        if (server_filter == ""):
            return (False, error_msg1)
        
        server_info = self.get_only_server_list(server_filter)

        server_info_matches = server_info.strip().split('\n')
        if len(server_info_matches) == 1:
            for server in self.server_info_list:
                if server_info_matches[0].lower() == server.str_info.lower():  
                    return (True, server)
        else:
            return (False, error_msg1 + f" which gives {len(server_info_matches)} servers\n{"\n".join(server_info_matches)}" )
    
    def request_server_start(self, server_filter=""):
        (search_success, info) = self.process_per_server_req(server_filter)
        if search_success:
            if info.status.lower() == "online":
                return f"Failed. \nRequested Server is already Online : \n{info.str_info}"
            else:
                # TODO call server start from here we can use server.id or something here
                return f"Success. \nRequesting Server start : \n{info.str_info}"
        else:
            return info

    def request_server_stop(self, server_filter=""):
        (search_success, info) = self.process_per_server_req(server_filter)
        if search_success:
            if info.status.lower() == "offline":
                return f"Failed. \nRequested Server is already offline : \n{info.str_info}"
            else:
                # TODO call server shutdown from here we can use server.id or something here
                return f"Success. \nDone Requesting Server stop : \n{info.str_info}"
        else:
            return info
    
    def request_server_restart(self, server_filter=""):
        (search_success, info) = self.process_per_server_req(server_filter)
        if search_success:
            if info.status.lower() == "offline":
                return f"Failed. \nDone Requested Server is offline call start instead? : \n{info.str_info}"
            else:
                # TODO call server start from here we can use server.id or something here
                return f"Success. \nDone Requesting Server restart : \n{info.str_info}"
        else:
            return info
        
    def request_server_update(self, server_filter=""):
        (search_success, info) = self.process_per_server_req(server_filter)
        if search_success:
            # TODO call server start from here we can use server.id or something here
            return f"Success. \nDone Requesting Server update : \n{info.str_info}"
        else:
            return info
        
if __name__ == "__main__":
    dasab_server_info = DASAB_SERVER_INFO_MANAGER()
    # print(dasab_server_info.get_server_list(''))
    # print(dasab_server_info.get_server_list('lost'))
    print(dasab_server_info.request_server_up('Dev'))
