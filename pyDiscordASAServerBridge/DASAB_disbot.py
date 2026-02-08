import discord
from discord import app_commands
from dotenv import load_dotenv
import os
import logging
import time
from functools import wraps
import asyncio
import inspect
import re

from utils import CommandConfigs, CooldownManager, load_json_file_with_comments
from DASAB_server_Info_manager import DASAB_SERVER_INFO_MANAGER
dasab_server_info = DASAB_SERVER_INFO_MANAGER()

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")
COMMAND_CONFIG_PATH = "DASAB_CFG_CMD.json"
RELOAD_ALLOWED_ROLES_ENV = "DASAB_RELOAD_ALLOWED_ROLES"

cmd_list = None
list_serv_cfg = None
req_serv_start_cfg = None
req_serv_stop_cfg = None
req_serv_restart_cfg = None
req_serv_update_cfg = None
rconcmd_cfg = None
runtime_command_configs = {}
SLASH_OPTION_NAME_PATTERN = re.compile(r"^[a-z0-9_-]{1,32}$")


def _get_config_by_name(source_cmd_list: CommandConfigs, command_name: str):
    if source_cmd_list is None:
        return None
    target_name = str(command_name or "").strip().casefold()
    for config in source_cmd_list.cmd_list:
        cfg_name = str(getattr(config, "_name", "") or "").strip().casefold()
        if cfg_name == target_name:
            return config
    return None


def _rebuild_runtime_command_lookup():
    runtime_command_configs.clear()
    if cmd_list is None:
        return
    for config in cmd_list.cmd_list:
        cfg_name = str(getattr(config, "_name", "") or "").strip()
        if cfg_name:
            runtime_command_configs[cfg_name] = config


def _sanitize_option_name(value: object) -> str:
    if value is None:
        return ""
    option_name = str(value).strip().lower().replace(" ", "_")
    option_name = re.sub(r"[^a-z0-9_-]", "", option_name)
    if not SLASH_OPTION_NAME_PATTERN.match(option_name):
        return ""
    return option_name


def _build_argument_metadata(config, func):
    rename_kwargs = {}
    describe_kwargs = {}
    if config is None:
        return rename_kwargs, describe_kwargs

    arguments = getattr(config, "_arguments_dict", None)
    if not isinstance(arguments, dict):
        return rename_kwargs, describe_kwargs

    params = inspect.signature(func).parameters
    for param_name, arg_cfg in arguments.items():
        if param_name not in params or not isinstance(arg_cfg, dict):
            continue

        configured_name = _sanitize_option_name(arg_cfg.get("name"))
        if configured_name and configured_name != param_name:
            rename_kwargs[param_name] = configured_name

        description = str(arg_cfg.get("description", "") or "").strip()
        if description:
            describe_kwargs[param_name] = description[:100]

    return rename_kwargs, describe_kwargs


def _apply_command_configs(source_cmd_list: CommandConfigs):
    global cmd_list, list_serv_cfg, req_serv_start_cfg, req_serv_stop_cfg
    global req_serv_restart_cfg, req_serv_update_cfg, rconcmd_cfg

    cmd_list = source_cmd_list
    list_serv_cfg = _get_config_by_name(cmd_list, "server_list")
    req_serv_start_cfg = _get_config_by_name(cmd_list, "server_start")
    req_serv_stop_cfg = _get_config_by_name(cmd_list, "server_stop")
    req_serv_restart_cfg = _get_config_by_name(cmd_list, "server_restart")
    req_serv_update_cfg = _get_config_by_name(cmd_list, "server_update")
    rconcmd_cfg = _get_config_by_name(cmd_list, "send_command")
    _rebuild_runtime_command_lookup()


def _reload_command_configs_from_disk() -> int:
    data = load_json_file_with_comments(COMMAND_CONFIG_PATH)
    if not isinstance(data, dict):
        raise ValueError("DASAB_CFG_CMD.json root must be a JSON object.")
    commands = data.get("commands", [])
    if not isinstance(commands, list):
        raise ValueError("DASAB_CFG_CMD.json 'commands' must be a list.")
    default_controls = data.get("default_discord_controls", [])
    if default_controls is not None and not isinstance(default_controls, list):
        raise ValueError("DASAB_CFG_CMD.json 'default_discord_controls' must be a list.")

    new_cmd_list = CommandConfigs()
    _apply_command_configs(new_cmd_list)
    return len(runtime_command_configs)


_apply_command_configs(CommandConfigs())

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
        for attr in ("_name", "_description", "_controls_list")
    ):
        args = (config, *args)
        config = None

    checks = kwargs.pop("checks", None)
    if checks is None:
        checks = []
    elif not isinstance(checks, (list, tuple)):
        checks = [checks]

    if config is not None:
        kwargs.setdefault("name", config._name)
        kwargs.setdefault("description", config._description)

    COMMAND_GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None
    if COMMAND_GUILD:
        decorator = dasab_bot.tree.command(*args, guild=COMMAND_GUILD, **kwargs)
    else:
        decorator = dasab_bot.tree.command(*args, **kwargs)

    def wrapper(func):
        if config is not None:
            rename_kwargs, describe_kwargs = _build_argument_metadata(config, func)
            if rename_kwargs:
                func = app_commands.rename(**rename_kwargs)(func)
            if describe_kwargs:
                func = app_commands.describe(**describe_kwargs)(func)
        if config is not None:
            func = with_cooldown(config)(func)
        for check in reversed(checks):
            func = check(func)
        return decorator(func)

    return wrapper

cooldown_manager = CooldownManager()

def _role_matches_control(interaction: discord.Interaction, control) -> bool:
    required_role = str(getattr(control, "_role", "") or "").strip()
    if not required_role:
        return True
    member_roles = getattr(interaction.user, "roles", None)
    if not member_roles:
        return False

    if required_role.isdigit():
        role_id = int(required_role)
        return any(getattr(role, "id", None) == role_id for role in member_roles)

    required_name = required_role.casefold()
    return any(str(getattr(role, "name", "")).casefold() == required_name for role in member_roles)


def _get_reload_allowed_roles() -> list[str]:
    raw_value = os.getenv(RELOAD_ALLOWED_ROLES_ENV, "ArkServerBridgeAdmin")
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def _has_reload_access(interaction: discord.Interaction) -> bool:
    permissions = getattr(interaction.user, "guild_permissions", None)
    if permissions is not None and bool(getattr(permissions, "administrator", False)):
        return True

    member_roles = getattr(interaction.user, "roles", None) or []
    if not member_roles:
        return False

    role_names = {str(getattr(role, "name", "")).casefold() for role in member_roles}
    role_ids = {str(getattr(role, "id", "")) for role in member_roles}
    for allowed in _get_reload_allowed_roles():
        if allowed.isdigit():
            if allowed in role_ids:
                return True
            continue
        if allowed.casefold() in role_names:
            return True
    return False

def _scope_allows_control(interaction: discord.Interaction, control) -> bool:
    allowed_guilds = getattr(control, "_allowed_guild_ids_list", [])
    allowed_channels = getattr(control, "_allowed_channel_ids_list", [])
    if allowed_guilds and interaction.guild_id not in allowed_guilds:
        return False
    if allowed_channels and interaction.channel_id not in allowed_channels:
        return False
    return True

def _scope_denied_message(interaction: discord.Interaction, control) -> str:
    allowed_guilds = getattr(control, "_allowed_guild_ids_list", [])
    allowed_channels = getattr(control, "_allowed_channel_ids_list", [])
    if allowed_guilds and interaction.guild_id not in allowed_guilds:
        return "Command not allowed in this server."
    if allowed_channels and interaction.channel_id not in allowed_channels:
        return "Command not allowed in this channel."
    return "You cannot use this command here."

def _control_rank(control):
    success_cd = getattr(control, "_success_cooldown_float", 0.0)
    failure_cd = getattr(control, "_failure_cooldown_float", 0.0)
    lowest = min(success_cd, failure_cd)
    return (lowest, success_cd, failure_cd)

def resolve_control_for_interaction(config, interaction: discord.Interaction):
    controls = getattr(config, "_controls_list", []) if config is not None else []
    if not controls:
        return None, None

    role_matched_controls = []
    for control in controls:
        if _role_matches_control(interaction, control):
            role_matched_controls.append(control)

    if not role_matched_controls:
        return None, "You are missing the required role to use this command."

    allowed_controls = []
    for control in role_matched_controls:
        if _scope_allows_control(interaction, control):
            allowed_controls.append(control)

    if allowed_controls:
        selected = min(allowed_controls, key=_control_rank)
        return selected, None

    return None, _scope_denied_message(interaction, role_matched_controls[0])

def with_cooldown(config):
    config_name = str(getattr(config, "_name", "") or "").strip()

    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            active_config = runtime_command_configs.get(config_name, config)
            matched_control, deny_message = resolve_control_for_interaction(active_config, interaction)
            if deny_message:
                await interaction.response.send_message(deny_message, ephemeral=True)
                return False

            command_key = cooldown_manager.get_command_key(active_config, func.__name__, matched_control)
            now = time.monotonic()
            remaining = cooldown_manager.get_remaining(interaction.user.id, command_key, now)
            if remaining > 0:
                await interaction.response.send_message(f"{interaction.user.mention}, you are on cooldown. Try again in {remaining:.2f}s.", ephemeral=True)
                return False
            try:
                result = await func(interaction, *args, **kwargs)
                success = bool(result)
            except Exception:
                cooldown_seconds = cooldown_manager.get_cooldown_seconds(active_config, False, matched_control)
                cooldown_manager.set_cooldown(interaction.user.id, command_key, cooldown_seconds, time.monotonic())
                raise

            cooldown_seconds = cooldown_manager.get_cooldown_seconds(active_config, success, matched_control)
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
async def server_list(interaction: discord.Interaction):
    server_filter = ""
    if list_serv_cfg is not None and getattr(list_serv_cfg, "_backend_req_list", None):
        return await _run(
            interaction,
            lambda sf: dasab_server_info.execute_backend_req(
                sf,
                list_serv_cfg._backend_req_list,
                response_processing=getattr(list_serv_cfg, "_response_processing_dict", None),
                require_single_match=getattr(list_serv_cfg, "_require_single_match_bool", True),
            ),
            server_filter,
            "Requesed server list",
        )
    return await _run(
        interaction,
        dasab_server_info.get_cached_server_list_async,
        server_filter,
        "Requesed server list",
        use_thread=False,
    )

@slash_command(req_serv_start_cfg)
@app_commands.autocomplete(server_filter=server_autocomplete)
async def server_req_start(interaction: discord.Interaction, server_filter: str = ""):
    if req_serv_start_cfg is not None and getattr(req_serv_start_cfg, "_backend_req_list", None):
        return await _run(
            interaction,
            lambda sf: dasab_server_info.execute_backend_req(
                sf,
                req_serv_start_cfg._backend_req_list,
                response_processing=getattr(req_serv_start_cfg, "_response_processing_dict", None),
                require_single_match=getattr(req_serv_start_cfg, "_require_single_match_bool", True),
            ),
            server_filter,
            "Requested server start",
        )
    return await _run(interaction, dasab_server_info.request_server_start, server_filter, "Requested server start")

@slash_command(req_serv_stop_cfg)
@app_commands.autocomplete(server_filter=server_autocomplete)
async def server_req_stop(interaction: discord.Interaction, server_filter: str = ""):
    if req_serv_stop_cfg is not None and getattr(req_serv_stop_cfg, "_backend_req_list", None):
        return await _run(
            interaction,
            lambda sf: dasab_server_info.execute_backend_req(
                sf,
                req_serv_stop_cfg._backend_req_list,
                response_processing=getattr(req_serv_stop_cfg, "_response_processing_dict", None),
                require_single_match=getattr(req_serv_stop_cfg, "_require_single_match_bool", True),
            ),
            server_filter,
            "Requested server stop",
        )
    return await _run(interaction, dasab_server_info.request_server_stop, server_filter, "Requested server stop")

@slash_command(req_serv_restart_cfg)
@app_commands.autocomplete(server_filter=server_autocomplete)
async def server_req_restart(interaction: discord.Interaction, server_filter: str = ""):
    if req_serv_restart_cfg is not None and getattr(req_serv_restart_cfg, "_backend_req_list", None):
        return await _run(
            interaction,
            lambda sf: dasab_server_info.execute_backend_req(
                sf,
                req_serv_restart_cfg._backend_req_list,
                response_processing=getattr(req_serv_restart_cfg, "_response_processing_dict", None),
                require_single_match=getattr(req_serv_restart_cfg, "_require_single_match_bool", True),
            ),
            server_filter,
            "Requested server restart",
        )
    return await _run(interaction, dasab_server_info.request_server_restart, server_filter, "Requested server restart")

@slash_command(req_serv_update_cfg)
@app_commands.autocomplete(server_filter=server_autocomplete)
async def server_req_update(interaction: discord.Interaction, server_filter: str = ""):
    if req_serv_update_cfg is not None and getattr(req_serv_update_cfg, "_backend_req_list", None):
        return await _run(
            interaction,
            lambda sf: dasab_server_info.execute_backend_req(
                sf,
                req_serv_update_cfg._backend_req_list,
                response_processing=getattr(req_serv_update_cfg, "_response_processing_dict", None),
                require_single_match=getattr(req_serv_update_cfg, "_require_single_match_bool", True),
            ),
            server_filter,
            "Requested server update",
        )
    return await _run(interaction, dasab_server_info.request_server_update, server_filter, "Requested server update")

@slash_command(rconcmd_cfg)
@app_commands.autocomplete(server_filter=server_autocomplete)
async def send_command(interaction: discord.Interaction, server_filter: str, message: str):
    if rconcmd_cfg is not None and getattr(rconcmd_cfg, "_backend_req_list", None):
        return await _run(
            interaction,
            lambda sf: dasab_server_info.execute_backend_req(
                sf,
                rconcmd_cfg._backend_req_list,
                message=message,
                response_processing=getattr(rconcmd_cfg, "_response_processing_dict", None),
                require_single_match=getattr(rconcmd_cfg, "_require_single_match_bool", True),
            ),
            server_filter,
            "Requested command send",
        )
    await interaction.response.send_message("Failed. send_command has no backend_req configured.", ephemeral=True)
    return False

@slash_command(name="reload_discord_config", description="Reload JSON configs without restarting the bot")
async def reload_discord_config(interaction: discord.Interaction):
    if not _has_reload_access(interaction):
        await interaction.response.send_message("You are missing the required role to use this command.", ephemeral=True)
        return False

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        reloaded_commands = _reload_command_configs_from_disk()
        reloaded_servers = dasab_server_info.reload_server_configs()
        if not dasab_server_info.is_cache_refreshing():
            asyncio.create_task(dasab_server_info.refresh_server_list_cache())
        await interaction.followup.send(
            (
                "Success. Reloaded runtime config."
                f" Commands: {reloaded_commands}."
                f" Servers: {reloaded_servers}."
                " If command names/descriptions changed, restart bot to resync slash metadata."
            ),
            ephemeral=True,
        )
        return True
    except Exception as e:
        await interaction.followup.send(f"Failed. Could not reload configs: {e}", ephemeral=True)
        return False

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
