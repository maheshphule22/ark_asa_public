import requests
from dotenv import load_dotenv
import os
import asyncio
import time

class DASAB_SERVER_INFO:
    id = ""
    name = ""
    status = ""
    ip = ""
    port = ""
    map = ""
    player = ""
    maxPlayer = ""
    days = ""
    str_info = ""

    def __init__(self, server_id, data):
        attributes = data['data']['attributes']

        self.str_info += "> " + attributes['name']
        self.str_info += " | " + attributes['status']
        self.str_info += " | " + attributes['ip'] + ":" + str(attributes['port'])
        self.str_info += " | " + attributes['details']['map']
        self.str_info += " | " + str(attributes['players']) + "/" + str(attributes['maxPlayers'])
        self.str_info += " | Day:" + str(attributes['details']['time_i'])
        
        self.populate(
            server_id,
            attributes['name'],
            attributes['status'],
            attributes['ip'],
            str(attributes['port']),
            attributes['details']['map'],
            str(attributes['players']),
            str(attributes['maxPlayers']),
            str(attributes['details']['time_i'])
        )

    def populate(self, i_id, i_name, i_status, i_ip, i_port, i_map, i_player, i_maxPlayer, i_days):
        self.id         = i_id
        self.name       = i_name
        self.status     = i_status
        self.ip         = i_ip
        self.port       = i_port
        self.map        = i_map
        self.player     = i_player
        self.maxPlayer  = i_maxPlayer
        self.days       = i_days

class DASAB_SERVER_INFO_MANAGER:
    server_info_list = []
    def __init__(self):
        load_dotenv()
        self.server_id_list = os.getenv("SERVERS_TO_WATCH")
        self._cache_ttl_seconds = 120
        self._cache = {"ts": 0.0, "data": "", "refreshing": False}

    # TODO implement server listing locally instead of battlematrix for better performance
    def get_server_info(self, server_id = ""):
        url = f"https://api.battlemetrics.com/servers/{server_id}"
        try:
            response = requests.get(url)
            message = ""
            if response.status_code == 200:
                data = response.json()
                server = DASAB_SERVER_INFO(server_id, data)
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
        for server_id in self.server_id_list.split(','):
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
