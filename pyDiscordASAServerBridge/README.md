# pyDiscordASAServerBridge

Minimal prototype: Discord bot + Python backend. The discord bot can lists servers and requests a server to spin up.

## Prerequisites
- Python 3.10+
- A Discord bot token

## Install
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configurations - 2 - .env for simple and secrete configs; .json for advanced configs
- Copy `.env.example` to `.env`
- Fill in `DISCORD_TOKEN` and `DISCORD_GUILD_ID`
- Change `SERVERS_TO_WATCH` battlematrix ids of servers you want to watch [ TODO local implementation instead of battlematrix] 
- Command config: update `DASAB_CFG_CMD.json`
- Server info config: update `DASAB_CFG_SERVERS.json`

## Run bot
```
python DASAB_disbot.py
```

## Commands (Slash) - names configurable using json - seq is important
- `/server_list     <search string>` - list available servers having search string or all if search string is empty
- `/server_start    <search string>` - request server start
- `/server_stop     <search string>` - request server stop
- `/server_restart  <search string>` - request server restart
- `/server_update   <search string>` - request server update

## Notes
- This is a in-dev/prototype, feel free to report issues
- user should make discord bot for their own use and run python with that bot's token 

## Requiement Discussions / TODO:
- [Done] - Guild ID check -> also added channel checks 
- [Done] - Timeout to person before starting another server -> added configurable cooldown to all commands
- [Done] - Update/stop/restart server -> different role specific -> role and channels configurable in json
- RCON commands - admin role specific - send complete command on RCON
- [Backlog] non admin to admin requests : restart & dino wipe etc - message in different chat/ping admin & admin will run command
    - this can be done with normal discord means - admins then have to send requied commands as per their setup
- [Future] - watch server status for 2 hours and if no players => shutdown? - differnt list of server

## issues to solve
    first use give `Responce: Failed. No cached servers found for all servers.` - neeed to fix this