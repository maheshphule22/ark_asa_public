import discord
from discord import app_commands
from dotenv import load_dotenv
import os
import logging

from DASAB_serverInfo import DASAB_SERVER_INFO_MANAGER
dasab_server_info = DASAB_SERVER_INFO_MANAGER()

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")
role_list_servers = os.getenv("DISCORD_ROLE_LIST_SERVER")
role_request_server = os.getenv("DISCORD_ROLE_REQUEST_SERVER")

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

COMMAND_GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None
def slash_command(*args, **kwargs):
    if COMMAND_GUILD:
        return dasab_bot.tree.command(*args, guild=COMMAND_GUILD, **kwargs)
    return dasab_bot.tree.command(*args, **kwargs)

@slash_command(name='list_servers', description="Lists the server matching pattern or all")
@app_commands.checks.has_role(role_list_servers)
async def list_servers(interaction: discord.Interaction, search_filter: str = ""):
    await interaction.response.send_message("Getting Server List, this will take some time...")
    server_info = dasab_server_info.get_server_list(search_filter)
    if(search_filter != ""):
        await interaction.followup.send(f"Here is list of servers containing {search_filter} : \n {server_info} \nDone listing servers")
    else:
        await interaction.followup.send(f"Here is full server list: \n {server_info}\nDone listing servers")

@slash_command(name='request_server', description="Send request to start server")
@app_commands.checks.has_role(role_request_server)
async def request_server(interaction: discord.Interaction, search_filter: str = ""):
    await interaction.response.send_message("Getting Server List, this will take some time...")
    if(search_filter != ""):
        info = dasab_server_info.request_server_up(search_filter)
        message = f"Requesting server : {search_filter} : \nResponce: {info}"
    else:
        message = f"Please give name of server which will uniqly identify server from list, current input : {search_filter} :"
    await interaction.followup.send(message)

@dasab_bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message("You are missing the required role to use this command.", ephemeral=True)
    elif isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message("You are missing all required roles to use this command.", ephemeral=True)
    else:
        # Handle other types of errors
        await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)


dasab_bot.run(token, log_handler=dasab_log_handler, log_level=logging.DEBUG)
