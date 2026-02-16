import re
import os
import logging
import discord

from discord import app_commands
from discord.ext import commands, tasks

from utilities.database import retrieve_key, store_key


def get_current_changelog(file_path) -> (int, str):
    with open(file_path, "r") as file:
        content = file.read()

    # Regular expression to find changelog sections
    changelog_pattern = re.compile(
        r"## Changelog (\d+)(.*?)(?=## Changelog \d+|$)", re.DOTALL
    )

    changelogs = changelog_pattern.findall(content)

    if not changelogs:
        return None, None

    # Extract the latest changelog number and content
    latest_changelog = changelogs[-1]
    changelog_number = int(latest_changelog[0])
    changelog_content = latest_changelog[1].strip()

    return changelog_number, changelog_content


class Changelog(commands.Cog, name="ChangeLogCog"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.last_log = retrieve_key("LAST_CHANGELOG", 0)

        # Try Docker path first, then fall back to local development path
        docker_changelog_path = "/app/README.md"
        # Try to find README.md relative to the project root
        local_changelog_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "README.md"
        )
        
        if os.path.exists(docker_changelog_path):
            changelog_path = docker_changelog_path
        elif os.path.exists(local_changelog_path):
            changelog_path = local_changelog_path
        else:
            logging.warning(
                f"Could not find README.md at {docker_changelog_path} or {local_changelog_path}. Skipping changelog check."
            )
            return

        # Crack the data we need
        logging.info(f"Loading {changelog_path}")
        _d = get_current_changelog(changelog_path)
        if _d[0] is None or _d[1] is None:
            logging.warning("No changelog found in README.md")
            return
        
        cur_lognum = int(_d[0])
        cur_logstr = _d[1]

        logging.debug(
            f"Changelog is currently {cur_lognum}/{self.last_log}. Content was: {cur_logstr}"
        )

        if cur_lognum == int(self.last_log):
            # If they match, we're done and we can pack up
            logging.info("No new changelog to report.")
            return

        # This was simplified when i took out the fops bot feature system,
        # For boorubot, i'll just read a single changelog channel from maintenance
        ch_id = str(os.environ.get("BOORU_MAINTENANCE"))
        if not ch_id:
            logging.warning("No channel set for changelog alerts (BOORU_MAINTENANCE not set)")
            return

        channel = self.bot.get_channel(int(ch_id))
        if not channel:
            logging.warning(f"Could not find channel {ch_id}")
            return

        # Replace any placeholders in the changelog text
        cur_logstr_formatted = f"# Changelog {cur_lognum}\n" + cur_logstr.replace(
            "{{version}}", self.bot.version
        )

        # Post the changelog
        await channel.send(cur_logstr_formatted)

        # Update the db after posting
        store_key("LAST_CHANGELOG", cur_lognum)

        logging.info("Changelog done!")


async def setup(bot):
    await bot.add_cog(Changelog(bot))
