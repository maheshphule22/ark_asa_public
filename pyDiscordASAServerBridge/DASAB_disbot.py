import discord
from discord import app_commands
from dotenv import load_dotenv
import os
import logging
import time
from functools import wraps
import asyncio

from utils import CommandConfigs, CooldownManager
from DASAB_serverInfo import DASAB_SERVER_INFO_MANAGER
dasab_server_info = DASAB_SERVER_INFO_MANAGER()

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")

cmd_list = CommandConfigs()
# for cmd in cmd_list.cmd_list:
#     print(cmd)
list_serv_cfg = cmd_list.get_config_at(0)
req_serv_start_cfg = cmd_list.get_config_at(1)
req_serv_stop_cfg = cmd_list.get_config_at(2)
req_serv_restart_cfg = cmd_list.get_config_at(3)
req_serv_update_cfg = cmd_list.get_config_at(4)
rconcmd_cfg = cmd_list.get_config_at(5)

SERVER_LIST_REFRESH_INTERVAL_SECONDS = 180

dasab_log_handler = logging.FileHandler(filename='DASAB_logs.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True

class DASABot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild {guild.id}")
        else:
            await self.tree.sync()

dasab_bot = DASABot()

@dasab_bot.event
async def on_ready() -> None:
    print(f"Logged in as {dasab_bot.user} (id={dasab_bot.user.id})")
    if not hasattr(dasab_bot, "_server_list_refresh_task") or dasab_bot._server_list_refresh_task.done():
        dasab_bot._server_list_refresh_task = asyncio.create_task(
            dasab_server_info.run_cache_refresh_loop(SERVER_LIST_REFRESH_INTERVAL_SECONDS)
        )

def slash_command(config=None, *args, **kwargs):
    if config is not None and not all(
        hasattr(config, attr)
        for attr in ("_name", "_description", "_role", "_count_int", "_success_cooldown_float")
    ):
        args = (config, *args)
        config = None

    checks = kwargs.pop("checks", None)
    if checks is None:
        checks = []
    elif not isinstance(checks, (list, tuple)):
        checks = [checks]

    config_checks = []
    if config is not None:
        kwargs.setdefault("name", config._name)
        kwargs.setdefault("description", config._description)
        if config._role:
            config_checks.append(app_commands.checks.has_role(config._role))
        allowed_guilds = getattr(config, "_allowed_guild_ids_list", [])
        allowed_channels = getattr(config, "_allowed_channel_ids_list", [])
        if allowed_guilds or allowed_channels:
            async def _scope_check(interaction: discord.Interaction):
                if allowed_guilds and interaction.guild_id not in allowed_guilds:
                    raise app_commands.CheckFailure("Command not allowed in this server.")
                if allowed_channels and interaction.channel_id not in allowed_channels:
                    raise app_commands.CheckFailure("Command not allowed in this channel.")
                return True
            config_checks.append(app_commands.check(_scope_check))

    checks = [*config_checks, *checks]

    COMMAND_GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None
    if COMMAND_GUILD:
        decorator = dasab_bot.tree.command(*args, guild=COMMAND_GUILD, **kwargs)
    else:
        decorator = dasab_bot.tree.command(*args, **kwargs)

    def wrapper(func):
        if config is not None:
            func = with_cooldown(config)(func)
        for check in reversed(checks):
            func = check(func)
        return decorator(func)

    return wrapper

cooldown_manager = CooldownManager()

def with_cooldown(config):
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            command_key = cooldown_manager.get_command_key(config, func.__name__)
            now = time.monotonic()
            remaining = cooldown_manager.get_remaining(interaction.user.id, command_key, now)
            if remaining > 0:
                await interaction.response.send_message(f"{interaction.user.mention}, you are on cooldown. Try again in {remaining:.2f}s.", ephemeral=True)
                return False
            try:
                result = await func(interaction, *args, **kwargs)
                success = bool(result)
            except Exception:
                cooldown_seconds = cooldown_manager.get_cooldown_seconds(config, False)
                cooldown_manager.set_cooldown(interaction.user.id, command_key, cooldown_seconds, time.monotonic())
                raise

            cooldown_seconds = cooldown_manager.get_cooldown_seconds(config, success)
            cooldown_manager.set_cooldown(interaction.user.id, command_key, cooldown_seconds, time.monotonic())
            return result
        return wrapper
    return decorator

async def server_autocomplete(interaction: discord.Interaction, current: str):
    names = await dasab_server_info.get_autocomplete_names(current, limit=25)
    return [app_commands.Choice(name=name, value=name) for name in names]

async def _run(interaction: discord.Interaction, work_fn, server_filter: str, action_label: str, use_thread: bool = True):
    await interaction.response.send_message("Working on the request, this may take some time...")
    if use_thread:
        info = await asyncio.to_thread(work_fn, server_filter)
    else:
        result = work_fn(server_filter)
        info = await result if asyncio.iscoroutine(result) else result
    message = f"{action_label} : {server_filter} : \nResponce: {info}"
    await interaction.followup.send(message)
    return info.strip().lower().startswith("success.")

@slash_command(list_serv_cfg)
async def server_list(interaction: discord.Interaction, server_filter: str = ""):
    return await _run(interaction, dasab_server_info.get_cached_server_list_async, server_filter, "Requesed server list", use_thread=False)

@slash_command(req_serv_start_cfg)
@app_commands.autocomplete(server_filter=server_autocomplete)
async def server_req_start(interaction: discord.Interaction, server_filter: str = ""):
    return await _run(interaction, dasab_server_info.request_server_start, server_filter, "Requested server start")

@slash_command(req_serv_stop_cfg)
@app_commands.autocomplete(server_filter=server_autocomplete)
async def server_req_stop(interaction: discord.Interaction, server_filter: str = ""):
    return await _run(interaction, dasab_server_info.request_server_stop, server_filter, "Requested server stop")

@slash_command(req_serv_restart_cfg)
@app_commands.autocomplete(server_filter=server_autocomplete)
async def server_req_restart(interaction: discord.Interaction, server_filter: str = ""):
    return await _run(interaction, dasab_server_info.request_server_restart, server_filter, "Requested server restart")

@slash_command(req_serv_update_cfg)
@app_commands.autocomplete(server_filter=server_autocomplete)
async def server_req_update(interaction: discord.Interaction, server_filter: str = ""):
    return await _run(interaction, dasab_server_info.request_server_update, server_filter, "Requested server update")

@dasab_bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message("You are missing the required role to use this command.", ephemeral=True)
    elif isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message("You are missing all required roles to use this command.", ephemeral=True)
    elif isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f'{interaction.user.mention}, you are on cooldown. Try again in {error.retry_after:.2f} seconds.', ephemeral=True)
    elif isinstance(error, app_commands.CheckFailure):
        message = str(error) or "You cannot use this command here."
        await interaction.response.send_message(message, ephemeral=True)
    else:
        # Handle other types of errors
        await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)

dasab_bot.run(TOKEN, log_handler=dasab_log_handler, log_level=logging.DEBUG)
