import os
import imp
import discord
import logging

from discord.ext import commands, tasks

booru_scripts = imp.load_source(
    "booru_scripts", "boorubot/scripts/Booru_Scripts/booru_utils.py"
)


class BooruModqueue(commands.Cog, name="BooruModqueueCog"):
    def __init__(self, bot):
        self.bot = bot

        # Configure options and secrets
        self.api_key = os.environ.get("BOORU_KEY", "")
        self.api_user = os.environ.get("BOORU_USER", "")
        self.api_url = os.environ.get("BOORU_URL", "")

        # Get maintenance channel
        self.maintenance_channel_id = str(os.environ.get("BOORU_MAINTENANCE"))

    @commands.Cog.listener()
    async def on_ready(self):
        # Start the modqueue check task
        self.check_modqueue.start()

    @tasks.loop(hours=1)
    async def check_modqueue(self):
        """
        Check the modqueue every hour and report any items to the maintenance channel.
        """
        logging.info("Running modqueue check.")

        if not self.maintenance_channel_id:
            logging.warning(
                "No maintenance channel configured, skipping modqueue check."
            )
            return

        channel = self.bot.get_channel(int(self.maintenance_channel_id))
        if not channel:
            logging.warning(
                f"Could not find maintenance channel {self.maintenance_channel_id}."
            )
            return

        # Fetch modqueue items
        modqueue_items = booru_scripts.fetch_modqueue(
            self.api_url, self.api_key, self.api_user, limit=100
        )

        if not modqueue_items:
            logging.debug("Modqueue is empty.")
            return

        # Build report message
        report_lines = [f"**Modqueue Report ({len(modqueue_items)} items):**\n"]

        for post in modqueue_items:
            post_id = post.get("id", "Unknown")
            post_url = f"{self.api_url}/posts/{post_id}"
            status = post.get("status", "unknown")
            tags = post.get("tag_string", "no tags")

            # Truncate tags if too long
            if len(tags) > 100:
                tags = tags[:100] + "..."

            report_lines.append(
                f"- Post {post_id} ({status}): <{post_url}>\n  Tags: `{tags}`"
            )

        report = "\n".join(report_lines)

        # Check if report is too long for Discord (4000 character limit)
        if len(report) > 3900:  # Leave some buffer
            # Truncate and add note
            truncated_report = report[:3900]
            truncated_report += "\n\n... (report truncated due to length)"
            report = truncated_report

        try:
            await channel.send(report)
            logging.info(f"Sent modqueue report with {len(modqueue_items)} items.")
        except Exception as e:
            logging.error(f"Failed to send modqueue report: {e}")

    @check_modqueue.before_loop
    async def before_check_modqueue(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(BooruModqueue(bot))
