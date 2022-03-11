# NOTE: this file contains backports or unintroduced features of next versions of dpy (as for 1.7.3)
# TODO: nuke this file when Red is changed its version to support required features
import discord
from discord import Role
from discord.http import Route
from discord.utils import _bytes_to_base64_data


async def edit_role_icon(
    bot, role: Role, reason=None, icon: bytes = None, unicode_emoji: str = None
):
    """|coro|

    Changes specified role's icon

    Parameters
    -----------
    role: :class:`discord.Role`
        A role to edit
    icon: :class:`bytes`
        A :term:`py:bytes-like object` representing the image to upload.
    unicode_emoji: :class:`str`
        A unicode emoji to set
    reason: Optional[:class:`str`]
        The reason for editing this role. Shows up on the audit log.

    Raises
    -------
    Forbidden
        You do not have permissions to change the role.
    HTTPException
        Editing the role failed.
    InvalidArgument
        Wrong image format passed for ``icon``.
        :param bot:
    """
    if not icon and not unicode_emoji:
        raise discord.InvalidArgument("You must specify icon or unicode_emoji")
    fields = {
        "unicode_emoji": unicode_emoji,
        "icon": _bytes_to_base64_data(icon) if icon else icon,
    }

    r = Route(
        "PATCH", "/guilds/{guild_id}/roles/{role_id}", guild_id=role.guild.id, role_id=role.id
    )
    await bot.http.request(r, json=fields, reason=reason)
