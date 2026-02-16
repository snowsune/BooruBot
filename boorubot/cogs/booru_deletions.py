import os
import importlib.util
import yaml
import discord
import logging
import asyncio

from datetime import datetime
from typing import Dict, List, Tuple
from discord.ext import commands, tasks

from utilities.database import retrieve_key, store_key

# Load booru_scripts module using importlib
_script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "Booru_Scripts", "booru_utils.py")
spec = importlib.util.spec_from_file_location("booru_scripts", _script_path)
booru_scripts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(booru_scripts)


class BooruDeletions(commands.Cog, name="BooruDeletionsCog"):
    def __init__(self, bot):
        self.bot = bot

        # Configure options and secrets
        self.api_key = os.environ.get("BOORU_KEY", "")
        self.api_user = os.environ.get("BOORU_USER", "")
        self.api_url = os.environ.get("BOORU_URL", "")

        # Get maintenance channel
        self.maintenance_channel_id = str(os.environ.get("BOORU_MAINTENANCE"))

        # Load deletions from YAML file
        self.deletion_list = self.load_deletions()

    def load_deletions(self) -> Dict[str, str]:
        """
        Load deletions from the YAML configuration file.

        Returns:
            Dict[str, str]: Dictionary of {tag: reason} pairs
        """
        # Try multiple possible paths for the config file
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "config", "deletions.yaml"),
            os.path.join("/app", "boorubot", "config", "deletions.yaml"),
            os.path.join("/app", "config", "deletions.yaml"),
            "boorubot/config/deletions.yaml",
            "config/deletions.yaml",
        ]

        for config_path in possible_paths:
            try:
                if os.path.exists(config_path):
                    with open(config_path, "r") as file:
                        config = yaml.safe_load(file)
                        deletions = config.get("deletions", {})
                        logging.info(
                            f"Loaded {len(deletions)} deletion rules from {config_path}"
                        )
                        return deletions
            except (FileNotFoundError, yaml.YAMLError) as e:
                logging.debug(f"Could not load from {config_path}: {e}")
                continue
            except Exception as e:
                logging.debug(f"Unexpected error loading from {config_path}: {e}")
                continue

        # If no config file found, use default
        logging.warning("No deletions config file found, using default")
        return {"fayanna": "Character requested removal."}

    @commands.Cog.listener()
    async def on_ready(self):
        # Start the deletion check task
        self.check_and_delete_posts.start()

    @tasks.loop(minutes=15)
    async def check_and_delete_posts(self):
        """
        Check for posts that need to be deleted based on the deletion_list.
        Runs every 15 minutes.
        """
        logging.debug("Running check and delete posts task.")

        if not self.deletion_list:
            logging.debug("No items in deletion list, skipping.")
            return

        maintenance_channel = self.bot.get_channel(int(self.maintenance_channel_id))
        if not maintenance_channel:
            logging.warning(
                f"Could not find maintenance channel {self.maintenance_channel_id}."
            )
            return

        deleted_posts = []
        failed_deletions = []

        for tag, reason in self.deletion_list.items():
            logging.info(f"Checking for posts with tag '{tag}' for deletion.")

            # Fetch posts with the specified tag - use a high limit to get all posts
            posts_to_check = booru_scripts.fetch_images_with_tag(
                tag,
                self.api_url,
                self.api_key,
                self.api_user,
                limit=1000,  # High limit to get all posts
                random=False,
            )

            if not posts_to_check:
                logging.debug(f"No posts found with tag '{tag}'.")
                continue

            logging.info(f"Found {len(posts_to_check)} posts with tag '{tag}'.")

            for post in posts_to_check:
                post_id = post["id"]
                post_url = f"{self.api_url}/posts/{post_id}"

                logging.info(
                    f"Attempting to delete post {post_id} (tag: {tag}, reason: {reason})"
                )

                # Attempt to delete the post
                success = booru_scripts.delete_post(
                    post_id, self.api_url, self.api_key, self.api_user, reason=reason
                )

                if success:
                    deleted_posts.append(
                        f"Deleted <{post_url}> (tag: `{tag}`, reason: {reason})"
                    )
                    logging.info(f"Successfully deleted post {post_id}")
                else:
                    failed_deletions.append(
                        f"Failed to delete <{post_url}> (tag: `{tag}`, reason: {reason})"
                    )
                    logging.error(f"Failed to delete post {post_id}")

        # Report results to maintenance channel
        if deleted_posts or failed_deletions:
            report_lines = []

            if deleted_posts:
                report_lines.append("**Successfully deleted posts:**")
                report_lines.extend(deleted_posts[:10])  # Limit to first 10
                if len(deleted_posts) > 10:
                    report_lines.append(f"... and {len(deleted_posts) - 10} more")
                report_lines.append("")  # Empty line for spacing

            if failed_deletions:
                report_lines.append("**Failed deletions:**")
                report_lines.extend(failed_deletions[:10])  # Limit to first 10
                if len(failed_deletions) > 10:
                    report_lines.append(f"... and {len(failed_deletions) - 10} more")

            report = "\n".join(report_lines)

            # Check if report is too long for Discord (4000 character limit)
            if len(report) > 3900:  # Leave some buffer
                report = report[:3900] + "\n\n... (report truncated due to length)"

            try:
                await maintenance_channel.send(
                    f"**Automatic deletion report:**\n\n{report}"
                )
            except Exception as e:
                logging.error(f"Failed to send deletion report: {e}")
        else:
            logging.debug("No posts were deleted or failed during this check.")

    @check_and_delete_posts.before_loop
    async def before_check_and_delete_posts(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()

    @commands.command(name="list_deletions")
    @commands.has_permissions(administrator=True)
    async def list_deletions(self, ctx):
        """
        List all tags in the deletion list.
        """
        if not self.deletion_list:
            await ctx.send("No items in deletion list.")
            return

        deletion_list_text = "\n".join(
            [f"`{tag}`: {reason}" for tag, reason in self.deletion_list.items()]
        )
        await ctx.send(f"**Current deletion list:**\n{deletion_list_text}")

    @commands.command(name="manual_delete")
    @commands.has_permissions(administrator=True)
    async def manual_delete(self, ctx, post_id: int, *, reason: str = ""):
        """
        Manually delete a specific post.

        Usage: !manual_delete <post_id> [reason]
        Example: !manual_delete 12345 Character requested removal.
        """
        post_url = f"{self.api_url}/posts/{post_id}"

        logging.info(f"Manual deletion requested for post {post_id} by {ctx.author}")

        success = booru_scripts.delete_post(
            post_id, self.api_url, self.api_key, self.api_user, reason=reason
        )

        if success:
            await ctx.send(f"Successfully deleted <{post_url}> (reason: {reason})")

            # Also report to maintenance channel
            maintenance_channel = self.bot.get_channel(int(self.maintenance_channel_id))
            if maintenance_channel:
                await maintenance_channel.send(
                    f"**Manual deletion by {ctx.author}:**\nDeleted <{post_url}> (reason: {reason})"
                )
        else:
            await ctx.send(f"Failed to delete <{post_url}>")

    @commands.command(name="reload_deletions")
    @commands.has_permissions(administrator=True)
    async def reload_deletions(self, ctx):
        """
        Reload the deletion list from the YAML configuration file.
        """
        old_count = len(self.deletion_list)
        self.deletion_list = self.load_deletions()
        new_count = len(self.deletion_list)

        await ctx.send(
            f"Reloaded deletion list. {old_count} → {new_count} rules loaded."
        )


async def setup(bot):
    await bot.add_cog(BooruDeletions(bot))
