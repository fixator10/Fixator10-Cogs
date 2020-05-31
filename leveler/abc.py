from abc import ABC, abstractmethod
from typing import Optional
from logging import Logger
from io import BytesIO
from re import Match

from aiohttp import ClientSession
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClient
from redbot.core.bot import Red
from redbot.core import Config


class MixinMeta(ABC):
    """
    Base class for well behaved type hint detection with composite class.
    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    bot: Red
    log: Logger

    config: Config

    _db_ready: bool
    client: AsyncIOMotorClient
    db: AsyncIOMotorDatabase
    session: ClientSession

    @abstractmethod
    async def _create_user(self, user, server):
        raise NotImplemented

    @abstractmethod
    async def _is_mention(self, user) -> str:
        raise NotImplemented

    @abstractmethod
    async def _hex_to_rgb(self, hex_num: str, a: int) -> tuple:
        raise NotImplemented

    @abstractmethod
    async def _rgb_to_hex(self, rgb) -> str:
        raise NotImplemented

    @abstractmethod
    async def _badge_convert_dict(self, userinfo):
        raise NotImplemented

    @abstractmethod
    async def _process_purchase(self, ctx) -> bool:
        raise NotImplemented

    @abstractmethod
    async def _is_hex(self, color: str) -> Optional[Match]:
        raise NotImplemented

    @abstractmethod
    def bool_emojify(self, bool_var: bool) -> str:
        raise NotImplemented

    @abstractmethod
    async def _handle_levelup(self, user, userinfo, server, channel):
        raise NotImplemented

    @abstractmethod
    async def _required_exp(self, level: int) -> int:
        raise NotImplemented

    @abstractmethod
    async def _level_exp(self, level: int) -> int:
        raise NotImplemented

    @abstractmethod
    async def _find_level(self, total_exp) -> int:
        raise NotImplemented

    @abstractmethod
    async def _find_server_rank(self, user, server) -> int:
        raise NotImplemented

    @abstractmethod
    async def _find_global_rank(self, user) -> int:
        raise NotImplemented

    @abstractmethod
    async def draw_profile(self, user, server) -> BytesIO:
        raise NotImplemented

    @abstractmethod
    async def draw_rank(self, user, server) -> BytesIO:
        raise NotImplemented

    @abstractmethod
    async def draw_levelup(self, user, server) -> BytesIO:
        raise NotImplemented
