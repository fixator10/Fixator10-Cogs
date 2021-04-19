import asyncio
from inspect import getsource
from logging import getLogger

import aiohttp
from redbot.core import Config, commands
from redbot.core.bot import Red

from .abc import CompositeMetaClass
from .commands import LevelerCommands
from .def_imgen_utils import DefaultImageGeneratorsUtils
from .exp import XP
from .image_generators import ImageGenerators
from .mongodb import MongoDB
from .utils import Utils

DISABLE_COG_IN_GUILD_ANNOTATIONS = {"cog_name": "str", "guild_id": "int", "return": "bool"}


class Leveler(
    MongoDB,
    XP,
    DefaultImageGeneratorsUtils,
    ImageGenerators,
    Utils,
    LevelerCommands,
    commands.Cog,
    metaclass=CompositeMetaClass,
):
    """A level up thing with image generation!"""

    __version__ = "3.0.0"

    # noinspection PyMissingConstructor
    def __init__(self, bot: Red):
        self.bot = bot
        self.log = getLogger("red.fixator10-cogs.leveler")
        self.config = Config.get_conf(self, identifier=0x3AAFD05EA4AA4FDF8DDEAD8224328191)
        default_mongodb = {
            "host": "localhost",
            "port": 27017,
            "username": None,
            "password": None,
            "db_name": "leveler",
        }
        default_global = {
            "bg_price": 0,
            "badge_type": "circles",
            "xp": [15, 20],
            "message_length": 10,
            "mention": True,
            "allow_global_top": False,
            "global_levels": False,
            "rep_rotation": False,
            "backgrounds": {
                "profile": {
                    "alice": "http://i.imgur.com/MUSuMao.png",
                    "abstract": "http://i.imgur.com/70ZH6LX.png",
                    "bluestairs": "http://i.imgur.com/EjuvxjT.png",
                    "lamp": "http://i.imgur.com/0nQSmKX.jpg",
                    "coastline": "http://i.imgur.com/XzUtY47.jpg",
                    "redblack": "http://i.imgur.com/74J2zZn.jpg",
                    "default": "http://i.imgur.com/8T1FUP5.jpg",
                    "iceberg": "http://i.imgur.com/8KowiMh.png",
                    "miraiglasses": "http://i.imgur.com/2Ak5VG3.png",
                    "miraikuriyama": "http://i.imgur.com/jQ4s4jj.png",
                    "mountaindawn": "http://i.imgur.com/kJ1yYY6.jpg",
                    "waterlilies": "http://i.imgur.com/qwdcJjI.jpg",
                },
                "rank": {
                    "aurora": "http://i.imgur.com/gVSbmYj.jpg",
                    "default": "http://i.imgur.com/SorwIrc.jpg",
                    "nebula": "http://i.imgur.com/V5zSCmO.jpg",
                    "mountain": "http://i.imgur.com/qYqEUYp.jpg",
                    "city": "http://i.imgur.com/yr2cUM9.jpg",
                },
                "levelup": {"default": "http://i.imgur.com/eEFfKqa.jpg"},
            },
        }
        default_guild = {
            "lvl_msg": False,
            "text_only": False,
            "private_lvl_message": False,
            "lvl_msg_lock": None,
            "msg_credits": 0,
            "ignored_channels": [],
        }
        self.config.init_custom("MONGODB", -1)
        self.config.register_custom("MONGODB", **default_mongodb)
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

        self._db_ready = False
        self._db_lock = asyncio.Lock()
        self.client = None
        self.db = None
        self.session = aiohttp.ClientSession()

        self._db_user_required_commands = [
            c.qualified_name
            for c in set(self.walk_commands())
            if "self.db.users" in getsource(c.callback)
        ]  # hacky way to get list of commands that requires users db

        self.bot.add_dev_env_value("leveler", lambda ctx: self)

    async def config_converter(self):
        """Update configs

        Versions:
        1. Remove disabled leveler and switch it to Red's disabled cogs system"""
        if not await self.config.config_version() or await self.config.config_version() < 1:
            self.log.info(
                'Converting config to v1: Moving disabled guilds to core\'s "command disablecog"...'
            )
            if not hasattr(self.bot, "_disabled_cog_cache") or not hasattr(
                self.bot._disabled_cog_cache, "disable_cog_in_guild"
            ):
                self.log.error(
                    "Unable to convert config: missing cog disable function."
                    "Please report this to cog author ASAP for fix."
                )
                return
            if (
                self.bot._disabled_cog_cache.disable_cog_in_guild.__annotations__
                != DISABLE_COG_IN_GUILD_ANNOTATIONS
            ):
                self.log.error(
                    "Unable to convert config: cog disable function annotations has changed. "
                    "Please report this to cog author ASAP for fix."
                )
                return
            for guild, data in (await self.config.all_guilds()).items():
                if data.get("disabled"):
                    self.log.info(f"Moving for guild {guild}")
                    await self.bot._disabled_cog_cache.disable_cog_in_guild(
                        self.qualified_name, guild
                    )
                await self.config.guild_from_id(guild).disabled.clear()
            self.log.info("Config updated to version 1")
            await self.config.config_version.set(1)

    async def initialize(self):
        await self.config_converter()
        await self._connect_to_mongo()

    async def cog_check(self, ctx):
        if (ctx.command.parent is self.levelerset) or ctx.command is self.levelerset:
            return True
        return self._db_ready

    async def cog_before_invoke(self, ctx):
        # creates user if not exists
        if ctx.command.qualified_name in self._db_user_required_commands:
            await self._create_user(ctx.author, ctx.guild)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        self._disconnect_mongo()
        self.bot.remove_dev_env_value("leveler")

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        await self.db.users.delete_one({"user_id": str(user_id)})
