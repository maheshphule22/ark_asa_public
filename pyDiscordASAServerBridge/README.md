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

## Configure
- Copy `.env.example` to `.env`
- Fill in `DISCORD_TOKEN`
- Change `DISCORD_ROLE_LIST_SERVER` and `DISCORD_ROLE_REQUEST_SERVER` as per your discord settings
- Change `SERVERS_TO_WATCH` battlematrix ids of servers you want to watch [ TODO local implementation instead of battlematrix] 

## Run bot
```
python DASAB_disbot.py
```

## Commands (Slash)
- `/list_servers` list available servers
- `/request <server>` ? request a server

## Notes
- This is a minimal prototype.
