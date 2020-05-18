from abc import ABC

from aiohttp import ClientSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from redbot.core.bot import Red
from redbot.core import Config


class MixinMeta(ABC):
    """
    Base class for well behaved type hint detection with composite class.
    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    bot: Red
    font_file: str
    font_bold_file: str
    font_unicode_file: str
    config: Config
    _db_ready: bool
    db: AsyncIOMotorDatabase
    session: ClientSession