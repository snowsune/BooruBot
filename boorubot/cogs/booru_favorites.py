import os
import importlib.util
import discord
import logging
import asyncio

from discord import app_commands
from discord.ext import commands, tasks

from utilities.database import retrieve_key, store_key

# Load booru utility functions using importlib
_script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "Booru_Scripts", "booru_utils.py")
spec = importlib.util.spec_from_file_location("booru_scripts", _script_path)
booru_scripts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(booru_scripts)


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
        self.fav_ch_exclude = "-vore -gore -scat -watersports -irl"
        self.sfw_fav_ch_exclude = f"-rating:explicit -rating:questionable {self.fav_ch_exclude}"
        self.vore_fav_ch_exclude = self.fav_ch_exclude.replace("-vore", "vore")

        self._fav_channel_configs = [
            ("fav_ch", self.fav_ch, self.fav_ch_exclude),
            ("sfw_fav_ch", self.sfw_fav_ch, self.sfw_fav_ch_exclude),
            ("vore_fav_ch", self.vore_fav_ch, self.vore_fav_ch_exclude),
        ]
        self._fav_channel_rotate = 0

    @commands.Cog.listener()
    async def on_ready(self):
        self.check_new_favorites.start()

    @tasks.loop(minutes=2)  # Runs one at a time every 2 mins! Will do all three in 6min ish
    async def check_new_favorites(self):
        channel_key, channel_id, exclude_pattern = self._fav_channel_configs[
            self._fav_channel_rotate % len(self._fav_channel_configs)
        ]
        self._fav_channel_rotate += 1

        if channel_id is None:
            logging.debug(f"Skipping fav check for {channel_key}, channel not configured")
            return

        logging.debug(
            f"Checking favorites for {channel_key} ({channel_id}) with exclude pattern {exclude_pattern}"
        )

        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            logging.warning(f"Could not find favorites channel {channel_id}.")
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

            # Get the last favorite we saw
            last_fav = retrieve_key(f"{channel.name}_fav_{username}", default=None)

            # If no last_fav exists, we will assume it's the user's first time being tracked
            if last_fav is None:
                logging.info(
                    f"Tracking new favs for user {username} starting at {latest_favs[0]}"
                )

                # Store the most recent favorite as the last seen favorite
                store_key(f"{channel.name}_fav_{username}", latest_favs[0])
                continue  # Move to the next user

            # Find the position of last_fav in the latest_favs list
            try:
                last_fav_index = latest_favs.index(int(last_fav))
            except ValueError:
                logging.warning(
                    f"For user {username} found more than 10 unposted favs!"
                )
                # If last_fav is not in the list, post all 10 starting from the oldest
                for fav_id in reversed(
                    latest_favs
                ):  # reverse to post from the oldest first
                    post_url = f"{self.api_url}/posts/{fav_id}"
                    await channel.send(
                        f"**{username}** added a new favorite!\n{post_url}"
                    )

                # Update the last_fav to the newest favorite
                store_key(f"{channel.name}_fav_{username}", latest_favs[0])
                continue  # Move to the next user after posting

            # If last_fav is found, post only the favorites after it
            new_favs = latest_favs[
                :last_fav_index
            ]  # Only the ones more recent than last_fav
            if new_favs:
                for fav_id in reversed(
                    new_favs
                ):  # reverse to post from the oldest first
                    post_url = f"{self.api_url}/posts/{fav_id}"
                    await channel.send(
                        f"**{username}** added a new favorite!\n{post_url}"
                    )

                # Update the last_fav to the newest favorite
                store_key(f"{channel.name}_fav_{username}", new_favs[0])

            await asyncio.sleep(0)

    @app_commands.command(
        name="set_sfw_fav_channel",
        description="Sets the channel for SFW favorite notifications. Ty Tirga!",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_sfw_fav_channel(self, interaction: discord.Interaction):
        store_key("sfw_fav_ch", interaction.channel_id) # Set DB
        self.sfw_fav_ch = interaction.channel_id # Update now too
        self._fav_channel_configs[1] = ("sfw_fav_ch", self.sfw_fav_ch, self.sfw_fav_ch_exclude)

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
        self._fav_channel_configs[0] = ("fav_ch", self.fav_ch, self.fav_ch_exclude)

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
        self._fav_channel_configs[2] = ("vore_fav_ch", self.vore_fav_ch, self.vore_fav_ch_exclude)

        await interaction.response.send_message(
            f"Set Vore Fav Channel to {interaction.channel.mention}!"
        )


async def setup(bot):
    await bot.add_cog(FavoriteWatcher(bot))
