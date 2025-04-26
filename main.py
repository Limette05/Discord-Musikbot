import os
import nextcord
import asyncio
from nextcord.ext import commands

intents = nextcord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print("Logged in")


async def load():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            if filename.startswith('dev_'):
                pass
            else:
                bot.load_extension(f'cogs.{filename[:-3]}')

token = "your token"

async def main():
    await load()
    await bot.start(token)

asyncio.get_event_loop().run_until_complete(main())
