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
- `display_fields` supports fallback lists. Example:
```json
"name": ["name", "server_name", "server_profile"],
"ip": ["ip", "server_ip"],
"port": ["port", "server_port"]
```
- For server list responses, missing values can be filled from matching server entries in `DASAB_CFG_SERVERS.json`.

### Optional command response formatting
Each command in `DASAB_CFG_CMD.json` can include `response_processing` to format backend JSON responses:
```json
"response_processing": {
  "template": "{message}",
  "fields": {
    "message": ["message", "detail", "error"]
  }
}
```
- `template` supports placeholders like `{message}`.
- `fields` maps placeholders to response keys, fallback list, or dotted paths.

### Optional slash argument metadata
Each command can include an `arguments` block to rename/describe slash options:
```json
"arguments": {
  "server_filter": {
    "name": "server",
    "description": "Server name/profile to target."
  },
  "message": {
    "name": "rcon_message",
    "description": "RCON command text."
  }
}
```
- Keys (`server_filter`, `message`) must match function parameter names.
- This changes slash option names/descriptions when commands are synced.

### Optional single-match guard
Each command can set:
```json
"require_single_match": true
```
- Default behavior (when omitted) is `true`.
- When `true`, command execution fails unless `server_filter` resolves to exactly one server.
- Recommended: `false` for `server_list`, `true` for start/stop/restart/update/rcon style commands.

## Run bot
```
python DASAB_disbot.py
```

## Commands (Slash) - names configurable using json - seq is important
- `/server_list` - list all available servers
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
- [Done] - RCON commands - admin role specific - send complete command on RCON
- [Done] - 1 command - different roles - different cooldown
- [Backlog] non admin to admin requests : restart & dino wipe etc - message in different chat/ping admin & admin will run command
    - this can be done with normal discord means - admins then have to send requied commands as per their setup
- [Future] - watch server status for 2 hours and if no players => shutdown? - differnt list of server

## issues to solve
    first use give `Responce: Failed. No cached servers found for all servers.` - neeed to fix this
