# FOSNHU
# 2021, Fops Bot
# MIT License

import os
import sys
import asyncio
import logging
import random

import discordhealthcheck

import discord
from discord import Intents, app_commands
from discord.ext import commands

from .utilities.migrations import init_migrations


async def on_tree_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CommandOnCooldown):
        return await interaction.response.send_message(
            f"Command is currently on cooldown! Try again in **{error.retry_after:.2f}** seconds!",
            ephemeral=True,
        )
    elif isinstance(error, app_commands.MissingPermissions):
        return await interaction.response.send_message(
            f"You're missing permissions to use that",
            ephemeral=True,
        )
    elif isinstance(error, app_commands.MissingRole):
        return await interaction.response.send_message(
            f"You need the {error.missing_role} role to use this command!",
            ephemeral=True,
        )
    else:
        raise error


def init_db():
    try:
        # Initialize and run migrations
        init_migrations()
        logging.info("Database initialized and migrations applied successfully.")
        return True
    except Exception as e:
        logging.exception(f"Database initialization failed: {e}")
        return False


class FopsBot:
    def __init__(self):
        # Intents (new iirc)
        intents = Intents(messages=True, guilds=True)
        intents.message_content = True

        # Some local memory flags
        self.dbReady = False

        # Create our discord bot
        self.bot = commands.Bot(command_prefix="^", intents=intents)

        # Remove legacy help command
        self.bot.remove_command("help")

        # Register python commands
        self.bot.on_ready = self.on_ready
        # self.bot.on_message = self.on_message

        # Register our error handler
        self.bot.tree.on_error = on_tree_error

        # Get the build commit that the code was built with.
        self.version = str(os.environ.get("GIT_COMMIT"))  # Currently running version
        # Find out if we're running in debug mode, or not.
        self.debug = str(os.environ.get("DEBUG")).lower() in ("true", "1", "t")

        # Append our workdir to the path (for importing modules)
        self.workdir = "/app/fops_bot/"
        sys.path.append(self.workdir)

        # Setup logging.
        if self.debug:
            logging.basicConfig(
                stream=sys.stderr,
                level=logging.DEBUG,
                format="%(levelname)s:%(name)s: %(message)s",  # Include logger name in output
            )
            logging.debug("Running in debug mode.")
        else:
            logging.basicConfig(
                stream=sys.stderr,
                level=logging.INFO,
                format="%(levelname)s:%(name)s: %(message)s",  # Include logger name in output
            )
            logging.info("Running in prod mode.")

        # Append some extra information to our discord bot
        self.bot.version = self.version  # Package version with bot

        # DB Setup
        try:
            logging.info("Configuring DB and running migrations")
            self.dbReady = init_db()
        except Exception as e:
            logging.error(f"Could not configure the DB! Error was {e}")
            self.dbReady = False
        finally:
            logging.info("Done configuring DB")

    async def load_cogs(self):
        # Cog Loader!
        logging.info("Loading cogs...")
        for filename in os.listdir(self.workdir + "cogs"):
            logging.info(f"Found file {filename}, loading as extension.")
            if filename.endswith(".py") and not filename.startswith("_"):
                try:
                    await self.bot.load_extension(f"cogs.{filename[:-3]}")
                except Exception as e:
                    logging.fatal(f"Error loading {filename} as a cog, error: {e}")
        logging.info("Done loading cogs")

    async def on_ready(self):
        # Start health monitoring
        logging.info(
            "Preparing external monitoring (using discordhealthcheck https://pypi.org/project/discordhealthcheck/)"
        )
        self.healthcheck_server = await discordhealthcheck.start(self.bot)
        logging.info("Done prepping external monitoring")

        await self.bot.tree.sync()

    async def on_message(self, ctx):
        # hehe, sneaky every time
        logging.info(ctx)

    async def start_bot(self):
        logging.info(f"Using version {self.version}")

        if not self.dbReady:
            logging.error("Database not ready. Bot will not start.")
            return

        # Begin the cog loader
        await self.load_cogs()

        # Run the discord bot using our token.
        await self.bot.start(str(os.environ.get("BOT_TOKEN")))

    def run(self):
        asyncio.run(self.start_bot())
