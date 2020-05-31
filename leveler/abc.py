from abc import ABC, abstractmethod
from logging import Logger
from io import BytesIO

from aiohttp import ClientSession
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClient
from redbot.core.bot import Red
from redbot.core import Config
from redbot.core import commands


class MixinMeta(ABC):
    """
    Base class for well behaved type hint detection with composite class.
    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    bot: Red
    log: Logger

    font_file: str
    font_bold_file: str
    font_unicode_file: str

    config: Config

    _db_ready: bool
    client: AsyncIOMotorClient
    db: AsyncIOMotorDatabase
    session: ClientSession

    lvladmin: commands.Group

    @abstractmethod
    async def _create_user(self, user, server): ...

    @abstractmethod
    async def _is_mention(self, user) -> str: ...

    @abstractmethod
    async def _required_exp(self, level: int) -> int: ...

    @abstractmethod
    async def _level_exp(self, level: int) -> int: ...

    @abstractmethod
    async def _find_level(self, total_exp) -> int: ...

    @abstractmethod
    async def draw_profile(self, user, server) -> BytesIO: ...

    @abstractmethod
    async def draw_rank(self, user, server) -> BytesIO: ...

    @abstractmethod
    async def draw_levelup(self, user, server) -> BytesIO: ...
