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
        _booru_channels = str(os.environ.get("BOORU_AUTO_UPLOAD")).split(",")
        self.fav_ch = _booru_channels[0]  # First channel in list is where favs go

    @commands.Cog.listener()
    async def on_ready(self):
        self.check_new_favorites.start()

    @tasks.loop(minutes=2)  # Run every other minute
    async def check_new_favorites(self):
        # Find the channel to post the updates
        channel = self.bot.get_channel(int(self.fav_ch))
        if not channel:
            logging.warning(f"Could not find favorites channel {channel}.")
            return

        # Fetch all users with favorites
        users_with_favs = booru_scripts.fetch_usernames_with_favs(
            self.api_url, self.api_key, self.api_user, limit=100
        )

        for username in users_with_favs:
            # Fetch the last 10 or so favorites for the user
            latest_favs = booru_scripts.fetch_user_favorites(
                self.api_url, self.api_key, self.api_user, username, limit=10
            )

            if not latest_favs:
                continue  # If no favorites were fetched, move on to the next user

            # Get the last favorite we saw
            last_fav = retrieve_key(f"fav_{username}", default=None)

            # If no last_fav exists, we will assume it's the user's first time being tracked
            if last_fav is None:
                logging.info(
                    f"Tracking new favs for user {username} starting at {latest_favs[0]}"
                )

                # Store the most recent favorite as the last seen favorite
                store_key(f"fav_{username}", latest_favs[0])
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
                store_key(f"fav_{username}", latest_favs[0])
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
                store_key(f"fav_{username}", new_favs[0])


async def setup(bot):
    await bot.add_cog(FavoriteWatcher(bot))
