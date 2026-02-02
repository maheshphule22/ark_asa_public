import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import logging
from DASAB_serverInfo import DASAB_SERVER_INFO_MANAGER

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
role_list_servers = os.getenv("DISCORD_ROLE_LIST_SERVER")
role_request_server = os.getenv("DISCORD_ROLE_REQUEST_SERVER")

dasab_log_handler = logging.FileHandler(filename='DASAB_logs.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

dasab_bot = commands.Bot(command_prefix='/', intents=intents)
dasab_server_info = DASAB_SERVER_INFO_MANAGER()

@dasab_bot.event
async def on_ready():
    print(f"We aready to go in, {dasab_bot.user.name} ")

@dasab_bot.command()
@commands.has_role(role_list_servers)
async def list_servers(ctx, *, search_filter=""):
    server_info = dasab_server_info.get_server_list(search_filter)
    if(search_filter != ""):
        message = f"{ctx.author.mention} here is list of servers containing {search_filter} : \n {server_info}"
    else:
        message = f"{ctx.author.mention} here is full server list: \n {server_info}"
    await ctx.reply(message)

@list_servers.error
async def list_servers_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.reply(f"{ctx.author.mention} you do not have permission to list servers.")    
    else:
        await ctx.reply(f"Unknown error : {error}")

@dasab_bot.command()
@commands.has_role(role_request_server)
async def request_server(ctx, *, search_filter=""):
    if(search_filter != ""):
        info = dasab_server_info.request_server_up(search_filter)
        message = f"{ctx.author.mention} Requesting server : {search_filter} : \nResponce: \n {info}"
    else:
        message = f"{ctx.author.mention} Please give name of server which will uniqly identify server from list, current input : {search_filter} :"
    await ctx.reply(message)

@request_server.error
async def request_server_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.reply(f"{ctx.author.mention} you do not have permission to request servers.")    
    else:
        await ctx.reply(f"Unknown error : {error}")    

dasab_bot.run(token, log_handler=dasab_log_handler, log_level=logging.DEBUG)

