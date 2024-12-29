import discord
import logging
import random
import asyncio
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime

from utilities.common import seconds_until

from utilities.database import store_key, retrieve_key


class ToolCog(commands.Cog, name="ToolsCog"):
    def __init__(self, bot):
        self.bot = bot
        self.command_counter = 0  # Initialize a command counter
        self.start_time = datetime.now()  # Track when the bot started

    @commands.Cog.listener()
    async def on_ready(self):
        # Start tasks
        self.update_status.start()
        self.reset_counter_task.start()

    @tasks.loop(minutes=1)  # Run every minute
    async def update_status(self):
        """
        Background task that updates the bot's status every minute, cycling between:
        - The bot's version
        - The number of guilds connected
        - The number of commands run today
        """

        statuses = [
            f"Version: {self.bot.version}",
            f"Connected to {len(self.bot.guilds)} guilds",
            f"Commands run today: {self.command_counter}",
        ]

        # Cycle through the statuses randomly
        new_status = random.choice(statuses)

        # Set the bot's activity status
        await self.bot.change_presence(activity=discord.Game(name=new_status))

    @commands.Cog.listener()
    async def on_app_command_completion(self, ctx, cmd):
        """
        Increment the command counter every time a command is run.
        """

        self.command_counter += 1

    @tasks.loop(count=1)
    async def reset_counter_task(self):
        """
        Task to reset the command counter at midnight, using the seconds_until function.
        """
        # Wait until midnight (00:00)
        seconds_to_midnight = seconds_until(0, 0)
        await asyncio.sleep(seconds_to_midnight)

        # Reset the command counter
        self.command_counter = 0
        logging.info("Command counter reset at midnight.")

        # Restart the loop to wait for the next midnight
        self.reset_counter_task.restart()

    @app_commands.command(name="version")
    async def version(self, ctx: discord.Interaction):
        """
        Prints the revision/version.
        """
        dbstatus = "Unknown"
        vc = None

        try:
            if True:
                try:
                    vc = retrieve_key("version_count", 0)
                    logging.info(f"Retrieved vc as {vc}")
                    dbstatus = "Ready"
                except Exception as e:
                    logging.error(f"Error retrieving key, error was {e}")
                    dbstatus = "Not Ready (connected but cant retrieve now)"

                store_key("version_count", int(vc) + 1)
            else:
                dbstatus = "Not Ready"
        except Exception as e:
            logging.error(f"Couldn't check db at all, error was {e}")

        await ctx.response.send_message(
            f"I am running version `{self.bot.version}`. DB is `{dbstatus}`, access `{vc}`"
        )


async def setup(bot):
    await bot.add_cog(ToolCog(bot))
