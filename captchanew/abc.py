from abc import ABC, abstractmethod
from typing import Dict, List

import discord
from discapty import Challenge
from redbot.core import Config
from redbot.core.bot import Red
from redbot.core.commands import Cog


class CogABC(ABC):
    bot: Red
    config: Config

    queue: Dict[int, Dict[int, Challenge]]
    """
    An internal queue, with:

    guild_id/        (int)

    ├─ user_id/      (int)

    │  ├─ Challenge
    """

    pending_queue: Dict[int, List[discord.Member]]
    """
    A list of pending challenges. The key is the guild's ID, inside, the IDs of pending users.
    """

    @abstractmethod
    def should_accept_challenge(self, guild: discord.Guild) -> bool:
        """
        Determine if the leaving messages should be send.
        It is mostly used in case of raiding event.
        """
        raise NotImplementedError()

    @abstractmethod
    async def start_challenge_for_member(self, member: discord.Member) -> Challenge:
        raise NotImplementedError()

    @abstractmethod
    def initiate_patch_note(self):
        """
        A method to call once the cog is loaded.
        Determine the logic for patchnote sending.
        """
        raise NotImplementedError()


class CogMixin(type(Cog), type(ABC)):  # type: ignore
    """
    Allows the metaclass used for proper type detection to coexist with discord.py's metaclass.
    Credit to https://github.com/Cog-Creators/Red-DiscordBot (mod cog) for mixin.
    """
