import os
import importlib.util
import discord
import logging
import asyncio

from discord import app_commands
from discord.ext import commands, tasks

from utilities.database import retrieve_key, store_key
from utilities.fav_announcements import announce_fav

# Load booru utility functions using importlib
_script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "Booru_Scripts", "booru_utils.py")
spec = importlib.util.spec_from_file_location("booru_scripts", _script_path)
booru_scripts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(booru_scripts)

FAV_TRACK_LIMIT = 3


def _load_seen_favs(value):
    """Unpacks seen favs"""
    if value is None:
        return []
    return [int(x) for x in str(value).split(",") if x.strip()]


def _save_seen_favs(fav_ids):
    """Packs seen favs"""
    return ",".join(str(fav_id) for fav_id in fav_ids[:FAV_TRACK_LIMIT])


def _new_favs_since_seen(latest_favs, seen_favs):
    """Newest-first IDs in latest that aren't in our tracked set, until we hit a known one."""
    seen_set = set(seen_favs)
    new_favs = []
    for fav_id in latest_favs:
        if fav_id in seen_set:
            break
        new_favs.append(fav_id)
    return new_favs


class FavoriteWatcher(commands.Cog, name="FavoriteWatcherCog"):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = os.getenv("BOORU_URL", "")
        self.api_key = os.getenv("BOORU_KEY", "")
        self.api_user = os.getenv("BOORU_USER", "")

        # Get channels
        self.fav_ch = retrieve_key("fav_ch", None)  # Channel for favs
        self.sfw_fav_ch = retrieve_key("sfw_fav_ch", None)  # Channel for SFW favs
        self.vore_fav_ch = retrieve_key("vore_fav_ch", None)  # Channel for vore favs

        # Exclude patterns
        self.base_exclude = "-vore -gore -scat -watersports -irl"
        self.fav_ch_exclude = f"{self.base_exclude} -rating:general"
        self.sfw_fav_ch_exclude = f"rating:general {self.base_exclude}"
        self.vore_fav_ch_exclude = self.base_exclude.replace("-vore", "vore")

        self._fav_channel_configs = [
            ("fav_ch", self.fav_ch, self.fav_ch_exclude),
            ("sfw_fav_ch", self.sfw_fav_ch, self.sfw_fav_ch_exclude),
            ("vore_fav_ch", self.vore_fav_ch, self.vore_fav_ch_exclude),
        ]
        self._fav_channel_rotate = 0

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_new_favorites.is_running():
            self.check_new_favorites.start()

    @tasks.loop(minutes=2)  # Runs one at a time every 2 mins! Will do all three in 6min ish
    async def check_new_favorites(self):
        channel_key, _, exclude_pattern = self._fav_channel_configs[
            self._fav_channel_rotate % len(self._fav_channel_configs)
        ]
        self._fav_channel_rotate += 1

        channel_id = retrieve_key(channel_key, None)
        if channel_id is None:
            logging.debug(f"Skipping fav check for {channel_key}, channel not configured")
            return

        logging.info(
            f"Checking favorites for {channel_key} ({channel_id}) with exclude pattern {exclude_pattern}"
        )

        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(channel_id))
            except discord.HTTPException as e:
                logging.warning(f"Could not find favorites channel {channel_id}: {e}")
                return

        users_with_favs = booru_scripts.fetch_usernames_with_favs(
            self.api_url,
            self.api_key,
            self.api_user,
            limit=100,
        )
        if not users_with_favs:
            return

        for username in users_with_favs:
            # Fetch the last 3 or so favorites for the user
            latest_favs = booru_scripts.fetch_user_favorites(
                self.api_url,
                self.api_key,
                self.api_user,
                username,
                limit=3,
                exclude=exclude_pattern,
            )

            if not latest_favs:
                continue  # If no favorites were fetched, move on to the next user

            # Get the last favorites we saw
            db_key = f"{channel_key}_fav_{username}"
            seen_favs = _load_seen_favs(retrieve_key(db_key, default=None))
            if not seen_favs:
                # Its probably an old key so, migrate by doing this
                seen_favs = _load_seen_favs(
                    retrieve_key(f"{channel.name}_fav_{username}", default=None)
                )
                if seen_favs:
                    store_key(db_key, _save_seen_favs(seen_favs))

            # If no history exists, its prolly the user's first time being tracked
            if not seen_favs:
                logging.info(
                    f"Tracking new favs for user {username} in {channel_key} starting at {latest_favs}"
                )

                # Store the most recent favorites as the last seen set
                store_key(db_key, _save_seen_favs(latest_favs))
                continue  # Move to the next user

            new_favs = _new_favs_since_seen(latest_favs, seen_favs)

            if new_favs and not set(seen_favs) & set(latest_favs):
                # If nothing in common, bad shift
                logging.warning(
                    f"Fav list reshuffled for {username} in {channel_key}: "
                    f"was {seen_favs}, now {latest_favs}"
                )
                store_key(db_key, _save_seen_favs(latest_favs))
                continue

            if new_favs:
                # Post only actual new favorites at the head of the list
                for fav_id in reversed(
                    new_favs
                ):  # reverse to post from the oldest first
                    logging.info(f"Posting fav {fav_id} from {username} to {channel_key}")
                    await announce_fav(
                        channel,
                        self.bot.user.id,
                        self.api_url,
                        username,
                        fav_id,
                    )

                store_key(db_key, _save_seen_favs(latest_favs))
            elif latest_favs != seen_favs[: len(latest_favs)]:
                # Head dropped off (unfav or re-tag)
                logging.warning(
                    f"Fav list rollback for {username} in {channel_key}: "
                    f"was {seen_favs}, now {latest_favs}"
                )
                store_key(db_key, _save_seen_favs(latest_favs))

            await asyncio.sleep(0)

    @check_new_favorites.before_loop
    async def before_check_new_favorites(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="set_sfw_fav_channel",
        description="Sets the channel for SFW favorite notifications. Ty Tirga!",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_sfw_fav_channel(self, interaction: discord.Interaction):
        store_key("sfw_fav_ch", interaction.channel_id) # Set DB
        self.sfw_fav_ch = interaction.channel_id # Update now too
        self._fav_channel_configs[1] = (
            "sfw_fav_ch",
            self.sfw_fav_ch,
            f"rating:general {self.base_exclude}",
        )

        await interaction.response.send_message(
            f"Set SFW Fav Channel to {interaction.channel.mention}!"
        )

    @app_commands.command(
        name="set_fav_channel",
        description="Sets the channel for favorite notifications. Ty Tirga!",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_fav_channel(self, interaction: discord.Interaction):
        store_key("fav_ch", interaction.channel_id) # Set DB
        self.fav_ch = interaction.channel_id # Update now too
        self._fav_channel_configs[0] = (
            "fav_ch",
            self.fav_ch,
            f"{self.base_exclude} -rating:general",
        )

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
        self.vore_fav_ch = interaction.channel_id # Update now too
        self._fav_channel_configs[2] = (
            "vore_fav_ch",
            self.vore_fav_ch,
            self.base_exclude.replace("-vore", "vore"),
        )

        await interaction.response.send_message(
            f"Set Vore Fav Channel to {interaction.channel.mention}!"
        )


async def setup(bot):
    await bot.add_cog(FavoriteWatcher(bot))
