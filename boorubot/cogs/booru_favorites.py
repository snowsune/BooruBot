import os
import json
import logging
import asyncio

import discord
import psycopg
from discord import app_commands
from discord.ext import commands

from utilities.database import retrieve_key, store_key
from utilities.fav_announcements import announce_fav
from utilities.danbooru_db import (
    FAVORITE_NOTIFY_CHANNEL,
    connect_async,
    fetch_fav_context,
    post_matches_filter,
)


class FavoriteWatcher(commands.Cog, name="FavoriteWatcherCog"):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = os.getenv("BOORU_URL", "")

        self.fav_ch = retrieve_key("fav_ch", None)
        self.sfw_fav_ch = retrieve_key("sfw_fav_ch", None)
        self.vore_fav_ch = retrieve_key("vore_fav_ch", None)

        self.base_exclude = "-vore -gore -scat -watersports -irl"
        self.fav_ch_exclude = f"{self.base_exclude} -rating:general"
        self.sfw_fav_ch_exclude = f"rating:general {self.base_exclude}"
        self.vore_fav_ch_exclude = self.base_exclude.replace("-vore", "vore")

        self._fav_channel_configs = [
            ("fav_ch", self.fav_ch_exclude),
            ("sfw_fav_ch", self.sfw_fav_ch_exclude),
            ("vore_fav_ch", self.vore_fav_ch_exclude),
        ]
        self._listen_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        if self._listen_task is None or self._listen_task.done():
            self._listen_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self):
        await self.bot.wait_until_ready()
        logging.info(f"Listening for favorites on {FAVORITE_NOTIFY_CHANNEL}")

        while not self.bot.is_closed():
            try:
                async with await connect_async() as conn:
                    await conn.execute(f"LISTEN {FAVORITE_NOTIFY_CHANNEL}")
                    async for notify in conn.notifies():
                        try:
                            payload = json.loads(notify.payload)
                            logging.info(f"Received favorite notification: {payload}")
                            await self._handle_favorite(payload)
                        except Exception:
                            logging.exception("Failed to handle favorite notification")
            except psycopg.Error as e:
                logging.warning(f"Favorites listener disconnected: {e}")
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.exception("Favorites listener error")

            if not self.bot.is_closed():
                await asyncio.sleep(5)

    async def _handle_favorite(self, payload):
        user_id = payload["user_id"]
        post_id = payload["post_id"]

        context = await fetch_fav_context(user_id, post_id)
        if not context:
            logging.warning(f"Could not load user/post for fav {payload}")
            return

        username, tag_string, rating = context
        posted = False

        for channel_key, filter_query in self._fav_channel_configs:
            if not post_matches_filter(tag_string, rating, filter_query):
                continue

            channel_id = retrieve_key(channel_key, None)
            if channel_id is None:
                continue

            channel = self.bot.get_channel(int(channel_id))
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(int(channel_id))
                except discord.HTTPException as e:
                    logging.warning(f"Could not find favorites channel {channel_id}: {e}")
                    continue

            logging.info(f"Posting fav {post_id} from {username} to {channel_key}")
            await announce_fav(
                channel,
                self.bot.user.id,
                self.api_url,
                username,
                post_id,
                tag_string,
            )
            posted = True

        if not posted:
            logging.info(
                f"Favorite {post_id} from {username} did not match any configured channel"
            )

    @app_commands.command(
        name="set_sfw_fav_channel",
        description="Sets the channel for SFW favorite notifications. Ty Tirga!",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_sfw_fav_channel(self, interaction: discord.Interaction):
        store_key("sfw_fav_ch", interaction.channel_id)
        self.sfw_fav_ch = interaction.channel_id

        await interaction.response.send_message(
            f"Set SFW Fav Channel to {interaction.channel.mention}!"
        )

    @app_commands.command(
        name="set_fav_channel",
        description="Sets the channel for favorite notifications. Ty Tirga!",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_fav_channel(self, interaction: discord.Interaction):
        store_key("fav_ch", interaction.channel_id)
        self.fav_ch = interaction.channel_id

        await interaction.response.send_message(
            f"Set Fav Channel to {interaction.channel.mention}!"
        )

    @app_commands.command(
        name="set_vore_fav_channel",
        description="Sets the channel for vore favorite notifications. Ty Tirga!",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_vore_fav_channel(self, interaction: discord.Interaction):
        store_key("vore_fav_ch", interaction.channel_id)
        self.vore_fav_ch = interaction.channel_id

        await interaction.response.send_message(
            f"Set Vore Fav Channel to {interaction.channel.mention}!"
        )


async def setup(bot):
    await bot.add_cog(FavoriteWatcher(bot))
