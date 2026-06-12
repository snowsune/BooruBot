import logging
import re

from utilities.spoiler import format_link_with_cw

FAV_HISTORY_LIMIT = 20


def _fav_header(usernames):
    if len(usernames) == 1:
        names = f"**{usernames[0]}**"
    elif len(usernames) == 2:
        names = f"**{usernames[0]}** and **{usernames[1]}**"
    else:
        names = (
            ", ".join(f"**{name}**" for name in usernames[:-1])
            + f", and **{usernames[-1]}**"
        )
    return f"{names} added a new favorite!"


def parse_fav_message(content):
    """If the content of the message is a fav announcement, return (post_id, usernames, link_section)"""
    lines = content.strip().splitlines()
    if len(lines) < 2:
        return None

    header, link_section = lines[0], "\n".join(lines[1:]).strip()
    if " added a new favorite!" not in header:
        return None

    post_match = re.search(r"/posts/(\d+)", link_section)
    if not post_match:
        return None

    names_part = header.split(" added a new favorite!")[0]
    usernames = re.findall(r"\*\*([^*]+)\*\*", names_part)
    if not usernames:
        return None

    return int(post_match.group(1)), usernames, link_section


def format_fav_message(usernames, link_section):
    return f"{_fav_header(usernames)}\n{link_section}"


def format_fav_announcement(usernames, post_url, tag_string=""):
    link_section = format_link_with_cw(post_url, tag_string)
    return format_fav_message(usernames, link_section)


def merge_fav_announcement(parsed, username):
    """Return updated message content, or None if username is already listed."""
    post_id, usernames, link_section = parsed
    if username in usernames:
        return None
    return format_fav_message(usernames + [username], link_section)


async def announce_fav(
    channel,
    bot_user_id,
    api_url,
    username,
    fav_id,
    tag_string="",
    history_limit=FAV_HISTORY_LIMIT,
):
    """Post a fav announcement, or edit a recent one for the same post."""
    import discord

    post_url = f"{api_url}/posts/{fav_id}"

    try:
        async for message in channel.history(limit=history_limit):
            if message.author.id != bot_user_id:
                continue

            parsed = parse_fav_message(message.content)
            if parsed is None:
                continue

            post_id, _, _ = parsed
            if post_id != fav_id:
                continue

            merged = merge_fav_announcement(parsed, username)
            if merged is None:
                return

            await message.edit(content=merged)
            logging.info(f"Updated fav {fav_id} announcement to include {username}")
            return
    except discord.HTTPException as e:
        logging.warning(f"Could not scan fav channel history: {e}")

    await channel.send(format_fav_announcement([username], post_url, tag_string))
