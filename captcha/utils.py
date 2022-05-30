from typing import List

import discord
from redbot.core.utils import chat_formatting as form


async def check_permissions_in_channel(permissions: List[str], channel: discord.TextChannel):
    """Function to checks if the permissions are available in a guild.
    This will return a list of the missing permissions.
    """
    return [
        permission
        for permission in permissions
        if not getattr(channel.permissions_for(channel.guild.me), permission)
    ]


def build_kick_embed(guild: discord.Guild, reason: str):
    embed = discord.Embed(
        title=f"You have been kicked from {guild.name}.",
        description="",
        color=discord.Colour.red().value,
    )
    embed.add_field(name="Reason:", value=reason)
    return embed


async def build_embed_with_missing_permissions(permissions: List[str]):
    embed = discord.Embed(
        title="Missing required permissions.",
        description=(
            form.warning(
                "In order to allow to set this parameter, you must give the bot the following "
                "permissions."
            )
        ),
        colour=discord.Colour.red().value,
    )
    strmissing = ""
    for perm in permissions:
        strmissing += "".join(("\n", form.inline(perm.replace("_", " ").capitalize())))
    embed.add_field(
        name=f"Missing permission{'s' if len(permissions) > 1 else ''}:", value=strmissing
    )
    return embed


async def build_embed_with_missing_settings(settings: List[str]):
    embed = discord.Embed(
        title="Missing required settings.",
        description=(
            form.warning(
                "In order to allow to set this parameter, you must set the following settings."
            )
        ),
        colour=discord.Colour.red().value,
    )
    strmissing = ""
    for setting in settings:
        strmissing += "".join(("\n", form.inline(setting.replace("_", " ").capitalize())))
    embed.add_field(name=f"Missing setting{'s' if len(settings) > 1 else ''}:", value=strmissing)
    return embed
