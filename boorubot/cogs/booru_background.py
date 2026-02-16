import os
import json
import importlib.util
import discord
import logging
import aiohttp
import asyncio

from datetime import datetime
from typing import Optional
from discord import app_commands
from discord.ext import commands, tasks

from saucenao_api import SauceNao
from saucenao_api.errors import SauceNaoApiError

from utilities.database import retrieve_key, store_key

# Load booru_scripts module using importlib
_script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "Booru_Scripts", "booru_utils.py")
spec = importlib.util.spec_from_file_location("booru_scripts", _script_path)
booru_scripts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(booru_scripts)


class BackgroundBooru(commands.Cog, name="BooruBackgroundCog"):
    def __init__(self, bot):
        self.bot = bot

        # Configure options and secrets
        self.api_key = os.environ.get("BOORU_KEY", "")
        self.api_user = os.environ.get("BOORU_USER", "")
        self.api_url = os.environ.get("BOORU_URL", "")

        # Configure SauceNAO
        self.sauce_api_key = os.environ.get("SAUCENAO_API_KEY", "")
        self.sauce = SauceNao(api_key=self.sauce_api_key)

        # Get channels
        _booru_channels = str(os.environ.get("BOORU_AUTO_UPLOAD")).split(",")
        self.fav_ch = _booru_channels[0]  # First channel in list is where favs go
        self.maintenance_channel_id = str(os.environ.get("BOORU_MAINTENANCE"))
        self.alert_channel_id = str(os.environ.get("ALERT_CHAN_ID", ""))

    @commands.Cog.listener()
    async def on_ready(self):
        # Start tasks
        self.update_status.start()
        self.check_new_comments.start()
        self.check_and_report_posts.start()
        self.check_modqueue.start()

    def check_reply(self, message):
        try:
            if message.reference is None:
                logging.debug("Message is not a reference")
                return False
            referenced_message = message.reference.resolved
            if referenced_message is None:
                logging.debug("Referenced message is None")
                return False
            if referenced_message.author.id != self.bot.user.id:
                logging.debug("Referenced message is not the bot user")
                return False
            # Check if the message starts with a valid post ID (assuming it's a number)
            try:
                post_id = int(referenced_message.content.split()[0])
                return True
            except ValueError:
                logging.warning(
                    f"Couldn't translate the first portion of message into an ID, issue was {int(referenced_message.content.split()[0])}"
                )
                return False
        except IndexError as e:
            logging.warning(
                f"Index error when splitting reply, this is usually because a user replied with a gif or embed. Message was {message}"
            )
            return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if self.check_reply(message):
            logging.info("Checked reply")
            referenced_message = message.reference.resolved
            # Extract the post ID from the first line of the original message
            post_id_line = referenced_message.content.splitlines()[0]
            try:
                post_id = int(
                    post_id_line.split()[-1]
                )  # Assuming the post ID is the last part of the first line
            except ValueError:
                return  # Invalid post ID format

            # Extract tags from the user's reply
            tags = message.content.split(" ")
            applied_tags = await self.append_tags(post_id, tags)

            # Thanks!
            await message.add_reaction("🙏")

            # Check if source was provided
            source_url = None
            for tag in tags:
                if tag.startswith("source:"):
                    source_url = tag.split(":", 1)[
                        1
                    ]  # Get the URL part after "source:"

            if source_url:
                booru_scripts.append_source_to_post(
                    post_id,
                    source_url.strip(),
                    self.api_url,
                    self.api_key,
                    self.api_user,
                )

                booru_scripts.append_post_tags(
                    post_id,
                    "",
                    self.api_url,
                    self.api_key,
                    self.api_user,
                    [
                        "missing_source"
                    ],  # Will remove missing_source tag if we apply a source
                )

                logging.info(f"Source URL {source_url} appended to post {post_id}")
                await message.add_reaction(
                    "🔗"
                )  # React with a link emoji to indicate the source was added

            # No tagme? yayy
            if "tagme" not in booru_scripts.get_post_tags(
                post_id,
                self.api_url,
                self.api_key,
                self.api_user,
            ):
                await message.add_reaction("✨")

    async def append_tags(self, post_id, tags):
        real_tags = []

        for tag in tags:
            if (
                booru_scripts.tag_exists(
                    tag,
                    self.api_url,
                    self.api_key,
                    self.api_user,
                )
                or "art:" in tag
            ):
                real_tags.append(tag)

        booru_scripts.append_post_tags(
            post_id,
            real_tags,
            self.api_url,
            self.api_key,
            self.api_user,
        )

        logging.info(f"Added {real_tags} to {post_id}")

        # If the number of tags is over 8 we can clear the `tagme`
        if (
            len(
                booru_scripts.get_post_tags(
                    post_id,
                    self.api_url,
                    self.api_key,
                    self.api_user,
                )
            )
            > 8
        ):
            logging.info("Clearing tagme")
            booru_scripts.append_post_tags(
                post_id,
                real_tags,
                self.api_url,
                self.api_key,
                self.api_user,
                ["tagme"],
            )

        return real_tags

    async def add_source_to_post(self, post_id, source_url, message):
        booru_scripts.append_source_to_post(
            post_id, source_url, self.api_url, self.api_key, self.api_user
        )
        booru_scripts.append_post_tags(
            post_id, "", self.api_url, self.api_key, self.api_user, ["missing_source"]
        )
        await message.add_reaction("🔗")

    @tasks.loop(minutes=10)
    async def update_status(self):
        maintenance_channel_id = str(os.environ.get("BOORU_MAINTENANCE"))
        if not maintenance_channel_id:
            return

        channel = self.bot.get_channel(int(maintenance_channel_id))
        if not channel:
            logging.warn(
                f"Could not find maintenance channel {maintenance_channel_id}."
            )
            return

        last_message = await channel.history(limit=1).__anext__()
        if last_message and last_message.author == self.bot.user:
            logging.debug("Last message was posted by the bot, skipping...")
            return

        r_post = booru_scripts.fetch_images_with_tag(
            "tagme", self.api_url, self.api_key, self.api_user, limit=1, random=True
        )[0]

        post_url = f"{self.api_url}/posts/{r_post['id']}"
        image_url = booru_scripts.get_image_url(
            r_post["id"], self.api_url, self.api_key, self.api_user
        )

        sauce_info = await self.get_sauce_info(channel, image_url)
        message = f"{r_post['id']}\n\n{post_url}"
        if sauce_info.get("source"):
            message += f"\n\nFound author and source `art:{sauce_info.get('author')} source:{sauce_info.get('source')}` via SauceNAO."

        await channel.send(message)

    async def get_sauce_info(self, channel, image_url):
        try:
            results = self.sauce.from_url(image_url)
            if results and results[0].similarity >= 80:
                author = results[0].author or "Unknown (checked with SauceNAO)"
                source = results[0].urls[0] if results[0].urls else "No source found"
                return {"author": author.replace(" ", "_"), "source": source}
        except SauceNaoApiError as e:
            logging.error(f"SauceNAO error: {str(e)}")
            await channel.send(f"Error using SauceNAO: {e}")

        return {"author": None, "source": None}

    @tasks.loop(seconds=30)
    async def check_new_comments(self):
        channel = self.bot.get_channel(int(self.fav_ch))
        if not channel:
            logging.warn(f"Could not find auto upload channel {self.fav_ch}")
            return

        last_comment_id = retrieve_key("last_comment_id", 0) or 0
        new_comments = booru_scripts.fetch_new_comments(
            self.api_url,
            self.api_key,
            self.api_user,
            last_comment_id=last_comment_id,
        )

        if new_comments:
            if last_comment_id != 0:
                for comment in new_comments:
                    _username = booru_scripts.get_username(
                        self.api_url,
                        self.api_key,
                        self.api_user,
                        comment["creator_id"],
                    )
                    await channel.send(
                        f"New comment by {_username} on post {comment['post_id']}:\n{comment['body']}\n\n{self.api_url}/posts/{comment['post_id']}"
                    )
            else:
                # Last comment id was 0! So we're skipping/new db.. either way.. DONT post all the comments!
                logging.warning(
                    f"Skipping posting {len(new_comments)} comments for now, as db was 0 or uninitialized."
                )

            store_key("last_comment_id", new_comments[0]["id"])

    @tasks.loop(minutes=30)
    async def check_and_report_posts(self):
        logging.debug(f"Running check and report posts.")

        changes = []

        posts_to_check = booru_scripts.fetch_images_with_tag(
            "missing_source OR missing_artist OR bad_link",
            self.api_url,
            self.api_key,
            self.api_user,
            limit=20,
            random=True,
        )

        for post in posts_to_check:
            post_id = post["id"]
            post_url = f"{self.api_url}/posts/{post_id}"

            if "missing_source" in post["tag_string"] and post["source"]:
                booru_scripts.append_post_tags(
                    post_id,
                    "",
                    self.api_url,
                    self.api_key,
                    self.api_user,
                    ["missing_source"],
                )
                changes.append(f"Removed `missing_source` from <{post_url}>")

            if "missing_artist" in post["tag_string"] and post["tag_string_artist"]:
                booru_scripts.append_post_tags(
                    post_id,
                    "",
                    self.api_url,
                    self.api_key,
                    self.api_user,
                    ["missing_artist"],
                )
                changes.append(f"Removed `missing_artist` from <{post_url}>")

            if "vore" not in post["tag_string"].split() and any(
                tag in post["tag_string"] for tag in ["vore", "unbirth"]
            ):
                booru_scripts.append_post_tags(
                    post_id, "vore", self.api_url, self.api_key, self.api_user
                )
                changes.append(f"Added `vore` to <{post_url}>")

        if changes:
            maintenance_channel_id = str(os.environ.get("BOORU_MAINTENANCE"))
            if not maintenance_channel_id:
                return

            channel = self.bot.get_channel(int(maintenance_channel_id))
            if not channel:
                logging.warn(f"Could not find maintenance channel!")
                return

            report = "\n".join(changes)
            await channel.send(f"Fixed some regular maintenance things:\n\n{report}")
        else:
            logging.info("No changes made during this check.")

    @tasks.loop(minutes=5)
    async def check_modqueue(self):
        """
        Check for new posts in the modqueue and alert on them.
        Runs every 5 minutes.
        """
        logging.info("Running modqueue check...")

        # Get channel to post to
        if not self.maintenance_channel_id:
            logging.warning("BOORU_MAINTENANCE not set, skipping modqueue check")
            return

        maintenance_channel = self.bot.get_channel(int(self.maintenance_channel_id))
        if not maintenance_channel:
            logging.warning(f"Could not find maintenance channel {self.maintenance_channel_id}")
            return

        # Fetch pending posts from modqueue
        try:
            pending_posts = booru_scripts.fetch_images_with_tag(
                "status:pending",
                self.api_url,
                self.api_key,
                self.api_user,
                limit=100,  # Get up to 100 pending posts
                random=False,
            )
            
            logging.info(f"Found {len(pending_posts)} pending posts in modqueue")
            
            # Debug: log all pending post IDs
            if pending_posts:
                post_ids = [post["id"] for post in pending_posts]
                logging.info(f"Pending post IDs: {post_ids}")
            else:
                logging.info("No pending posts found")
                return

            # Get the last modqueue ID we've already sent
            last_sent_id = retrieve_key("last_modqueue_id_sent", 0) or 0
            # Ensure it's an integer
            try:
                last_sent_id = int(last_sent_id)
            except (ValueError, TypeError):
                last_sent_id = 0
            logging.info(f"Last modqueue ID sent: {last_sent_id}")

            # Filter to only posts newer than the last one we sent
            # Sort by ID ascending to process oldest first
            new_posts = [
                post for post in pending_posts 
                if post["id"] > last_sent_id
            ]
            new_posts.sort(key=lambda x: x["id"])

            logging.info(f"Found {len(new_posts)} new pending posts (IDs > {last_sent_id})")

            # Alert on new posts
            if new_posts:
                highest_id = last_sent_id
                for post in new_posts:
                    post_id = post["id"]
                    post_url = f"{self.api_url}/posts/{post_id}"
                    
                    # Get post details for better logging
                    tags = post.get("tag_string", "no tags")
                    creator_id = post.get("uploader_id", "unknown")
                    
                    logging.info(
                        f"Alerting on new modqueue post {post_id} "
                        f"(tags: {tags}, creator: {creator_id})"
                    )
                    
                    await maintenance_channel.send(
                        f"**New post in modqueue:**\n"
                        f"Post ID: {post_id}\n"
                        f"Tags: {tags}\n"
                        f"Link: {post_url}"
                    )
                    
                    # Track the highest ID we've sent
                    if post_id > highest_id:
                        highest_id = post_id

                # Update the last sent ID to the highest one we just sent
                store_key("last_modqueue_id_sent", highest_id)
                logging.info(f"Updated last_modqueue_id_sent to {highest_id}")
            else:
                logging.debug(f"No new pending posts to alert on (all IDs <= {last_sent_id})")

        except Exception as e:
            logging.error(f"Error checking modqueue: {e}", exc_info=True)


async def setup(bot):
    await bot.add_cog(BackgroundBooru(bot))
