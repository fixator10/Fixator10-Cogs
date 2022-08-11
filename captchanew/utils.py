import logging
from typing import List, Optional, Union

import discord
from redbot.core import Config

from captchanew.contracts.config import GuildConfigContract

DEFAULT_GLOBAL = {"log_level": 50, "was_loaded_once": False, "migration": 0}
DEFAULT_GUILD: GuildConfigContract = {
    "channel": None,  # The channel where the captcha is sent.
    "logs_channel": None,  # Where logs are sent.
    "enabled": False,  # If challenges must be activated.
    "auto_roles": [],  # Roles to give.
    "temp_role": None,  # Temporary role to give.
    "type": "text",  # Captcha type.
    "timeout": 5,  # Time in minutes before kicking.
    "retries": 3,  # The number of retries allowed.
    "simultaneous_challenges": 5,
}


def get_config(with_defaults: bool = True) -> Config:
    """
    Return a config instance of the cog.

    Parameters
    ----------
    with_defaults : bool
        If the defaults values should be registered. (register_global, register_guild, ...)
        This will also set the ```force_registration``` when creating the Config instance.

    Returns
    -------
    Config :
        The Config instance.
    """
    conf = Config.get_conf(
        None, identifier=495954056, force_registration=with_defaults, cog_name="Captcha"
    )
    if with_defaults:
        conf.register_global(**DEFAULT_GLOBAL)
        conf.register_guild(**DEFAULT_GUILD)
    return conf


def get_log():
    return logging.getLogger("red.fixator10-cogs.captcha")


def log_write(message: str, level: int):
    log = get_log()
    log.log(level, message)


def get_missing_permissions(
    permissions: List[str],
    target: discord.Member,
    channel: Optional[Union[discord.TextChannel, discord.abc.GuildChannel]] = None,
) -> List[str]:
    """
    Return a list of missing permissions.

    Parameters
    ----------
    permissions : List[str]
        The permissions you require.
    target : discord.Member
        The member we're checking permissions for.
    channel : Optional[discord.TextChannel]
        The channel where we are checking the permissions.

    Returns
    -------
    List[str] :
        The missing permissions, if any.
    """
    if channel:
        check_against = channel.permissions_for(target)
    else:
        check_against = target.guild_permissions

    return [permission for permission in permissions if not getattr(check_against, permission)]
