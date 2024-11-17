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
            if filename.startswith('old_') or filename.startswith('dev_'):
                pass
            # if filename.startswith("test-cog"):
            #     bot.load_extension(f'cogs.{filename[:-3]}')
            else:
                bot.load_extension(f'cogs.{filename[:-3]}')


kleine_limette = "your token"


async def main():
    await load()
    await bot.start("MTA4NDI2ODYzOTAzOTAwMDYyOA.GUNSl4.55HxqEmiRLp2hhDsth8uT9CiqFZRrTi1m08ULI")

asyncio.get_event_loop().run_until_complete(main())
