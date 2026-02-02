# fix for latest versions of python, for below error we are getting for valve
# AttributeError: module 'collections' has no attribute 'Mapping'
# import collections
# if not hasattr(collections, 'Mapping'):
#     import collections.abc
#     collections.Mapping = collections.abc.Mapping
#     collections.MutableMapping = collections.abc.MutableMapping
#     collections.Sequence = collections.abc.Sequence
    
# import valve.source.a2s

#class DASAB_SERVER_INFO:
    # def get_server_info(self, SERVER_ADDRESS=("96.225.165.119", 7863)):
    # def get_server_info(self, SERVER_ADDRESS=("game.prisolis.com", 7803)):
    #     message = ""
    #     message = ""
    #     try:
    #         with valve.source.a2s.ServerQuerier(SERVER_ADDRESS, timeout=30) as server:
    #             info = server.info()
    #             players = server.players()
    #             message += f"\nServer Name: {info['server_name']}"
    #             message += f"\nPlayers: {info['player_count']}/{info['max_players']}"
    #             if players:
    #                 print("Player List:")
    #                 # Sort players by score in descending order
    #                 for player in sorted(players, key=lambda p: p.score, reverse=True):
    #                     print(f"  {player.score} {player.name}")
    #                       
    #     except Exception as e:
    #         message += f"Error querying server: {e}"
    #     return message
# above implementation was using valve but currently only getting timeout

import requests
from dotenv import load_dotenv
import os

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
    
    def get_server_list(self, search_filter=""):
        server_info = self.repopulate_all_server_list()
        if (search_filter != ""):
            server_info = ""
            for server in self.server_info_list:
                if (search_filter.lower() in server.str_info.lower()):
                    server_info += server.str_info + "\n"
        return server_info

    def request_server_up(self, search_filter=""):
        error_msg1 = f"Please give name of server which will uniqly identify server from list, current input : {search_filter} : "
        if (search_filter == ""): # we already have this check in bot also 
            return error_msg1

        server_info = self.get_server_list(search_filter)

        server_info_matches = server_info.strip().split('\n')
        if len(server_info_matches) == 1:
            for server in self.server_info_list:
                if server_info_matches[0].lower() == server.str_info.lower():  
                    if server.status.lower() == "online":
                        # TODO Requested Server is already online but do we still want to call start/restart?
                        return f"Requested Server is already online : \n{server.str_info}"
                    else:
                        # TODO call reserver startup from here we can use server.id or something here
                        return f"Requesting Server startup : \n{server.str_info}"
        else:
            return error_msg1 + f" which gives {len(server_info_matches)} servers\n{"\n".join(server_info_matches)}" 
    
if __name__ == "__main__":
    dasab_server_info = DASAB_SERVER_INFO_MANAGER()
    # print(dasab_server_info.get_server_list(''))
    # print(dasab_server_info.get_server_list('lost'))
    print(dasab_server_info.request_server_up('Dev'))