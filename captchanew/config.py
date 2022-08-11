from abc import ABC, abstractmethod
from copy import copy
from typing import Any, Dict, Iterable, List, Literal, Optional, Union

import discord
from redbot.core import commands

from .contracts.config import GuildConfigContract
from .errors import MissingRequiredPermissionsError, MissingRequiredSettingError
from .utils import get_config, get_missing_permissions


class BaseSettings(ABC, object):
    @property
    @abstractmethod
    def is_persisted(self) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def commit(self):
        raise NotImplementedError()

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError()


class GuildSettings(BaseSettings):
    _guild_id: int
    _original: GuildConfigContract

    _channel: Optional[Union[int, Literal["dm"]]]
    _logs_channel: Optional[int]

    enabled: bool
    timeout: int
    retries: int
    simultaneous_challenges: int

    _auto_roles: List[int]
    _temp_role: Optional[int]

    type: Literal["text", "wheezy", "image"]

    def __init__(self, guild_id: int, data: GuildConfigContract) -> None:
        self._guild_id = guild_id

        self._channel = data["channel"]
        self._logs_channel = data["logs_channel"]
        self._auto_roles = data["auto_roles"]
        self._temp_role = data["temp_role"]
        self.enabled = data["enabled"]
        self.type = data["type"]
        self.timeout = data["timeout"]
        self.retries = data["retries"]

        self._original = copy(self.to_dict())

    @property
    def data(self):
        return self.to_dict()

    @data.setter
    def data(self, data: Dict[str, Any]):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @property
    def auto_roles(self) -> List[int]:
        return self._auto_roles

    @auto_roles.setter
    def auto_roles(self, set_to: Iterable[Union[int, discord.Role]]):
        result: List[int] = []
        for role in set_to:
            if isinstance(role, discord.Role):
                result.append(role.id)
            else:
                result.append(role)
        self._auto_roles = result

    @property
    def temp_role(self):
        return self._temp_role

    @temp_role.setter
    def temp_role(self, role: Optional[Union[int, discord.Role]]):
        self._temp_role = role.id if isinstance(role, discord.Role) else role

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, channel: Union[Literal["dm"], int, discord.TextChannel]):
        self._channel = channel.id if isinstance(channel, discord.TextChannel) else channel

    @property
    def logs_channel(self):
        return self._logs_channel

    @logs_channel.setter
    def logs_channel(self, channel: Union[int, discord.TextChannel]):
        self._logs_channel = channel.id if isinstance(channel, discord.TextChannel) else channel

    def can_be_enabled(self, ctx: commands.GuildContext) -> bool:
        """
        Determine if the guild can activate the cog.

        Raises
        ------
        MissingRequiredSettingError :
            If a required setting is missing.
        MissingRequiredPermissionsError :
            If one or more permissions is missing.

        Returns
        -------
        bool :
            True if it can be enabled. Can only return True. False are errors to catch.
        """
        if not self.channel:
            raise MissingRequiredSettingError("channel", self.channel)

        if isinstance(self.channel, int):
            fetch_channel: Optional[discord.abc.GuildChannel] = ctx.bot.get_channel(
                self.channel
            )  # TODO: Remove typehint at d.py 2.0
            if not fetch_channel:
                raise MissingRequiredSettingError("channel", "Channel not found/deleted")

            required_perms = [
                "add_reactions",
                "embed_links",
                "manage_messages",
                "read_messages",
                "read_message_history",
                "send_messages",
                "attach_files",
            ]
            if missing_permissions := get_missing_permissions(
                required_perms, ctx.me, fetch_channel
            ):
                raise MissingRequiredPermissionsError(missing_permissions, str(fetch_channel))

        if (self.auto_roles or self.temp_role) and not ctx.me.guild_permissions.manage_roles:
            raise MissingRequiredPermissionsError(["manage_roles"])

        return True

    async def commit(self):
        """
        Save the new settings.
        """
        config = get_config()
        await config.guild_from_id(self._guild_id).set_raw(value=self.to_dict())
        self._original = self.to_dict()

    def erase(self):
        """
        Reset all settings to their defaults.
        This does NOT commit the changes.
        """
        config = get_config(with_defaults=True)
        defaults = config.guild_from_id(self._guild_id).defaults
        self.data = defaults

    def to_dict(self) -> GuildConfigContract:
        return GuildConfigContract(
            channel=self.channel,
            logs_channel=self.logs_channel,
            enabled=self.enabled,
            auto_roles=self.auto_roles,
            temp_role=self.temp_role,
            type=self.type,
            timeout=self.timeout,
            retries=self.retries,
            simultaneous_challenges=self.simultaneous_challenges,
        )

    @property
    def is_dirty(self):
        """
        Determine if the settings have been modified.

        Returns
        -------
        bool :
            If the settings have been modified.
        """
        return self._original != self.to_dict()

    @property
    def dirty(self) -> Dict[str, Any]:
        """
        Return the modified settings.

        Returns
        -------
        Dict[str, Any] :
            The dict containing the modified settings.
        """
        dirty_obj: Dict[str, Any] = {}
        new_values = self.to_dict()
        for key, actual_value in self._original.items():
            if (new_value := new_values[key]) != actual_value:
                dirty_obj[key] = new_value
        return dirty_obj

    @classmethod
    def from_data(cls, guild_id: int, data: GuildConfigContract):
        return cls(guild_id, data)

    @classmethod
    async def from_guild(cls, guild: discord.Guild):
        config = get_config()
        guild_data = await config.guild(guild).all()  # type: ignore
        return cls(guild.id, guild_data)

    @classmethod
    async def from_guild_id(cls, guild_id: int):
        config = get_config()
        guild_data = await config.guild_from_id(guild_id).all()  # type: ignore
        return cls(guild_id, guild_data)
