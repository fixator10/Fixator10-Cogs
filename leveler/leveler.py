import operator
import random
import time
from asyncio import TimeoutError as AsyncTimeoutError
from collections import OrderedDict
from logging import getLogger

import aiohttp
import discord
from redbot.core import Config, bank, checks, commands
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate

try:
    import numpy
    from scipy import cluster
except Exception as e:
    print(
        f"{__file__}: numpy/scipy is unable to import: {e}\nAutocolor feature will be unavailable"
    )

from .abc import CompositeMetaClass
from .commands import LevelerCommands
from .exp import XP
from .image_generators import ImageGenerators
from .mongodb import MongoDB
from .utils import Utils


class Leveler(
    MongoDB,
    XP,
    ImageGenerators,
    Utils,
    LevelerCommands,
    commands.Cog,
    metaclass=CompositeMetaClass,
):
    """A level up thing with image generation!"""

    __version__ = "2.2.0b1"

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
            "disabled": False,
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
        self.client = None
        self.db = None
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    async def initialize(self):
        await self._connect_to_mongo()

    async def cog_check(self, ctx):
        if (ctx.command.parent is self.levelerset) or ctx.command is self.levelerset:
            return True
        return self._db_ready

    async def cog_before_invoke(self, ctx):
        # creates user if not exists
        await self._create_user(ctx.author, ctx.guild)

    def cog_unload(self):
        self.session.detach()
        self._disconnect_mongo()

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        await self.db.users.delete_one({"user_id": str(user_id)})

    @commands.group(name="lvlset", pass_context=True)
    async def lvlset(self, ctx):
        """Profile configuration Options."""
        pass

    @lvlset.group(name="profile", pass_context=True)
    async def profileset(self, ctx):
        """Profile options."""
        pass

    @lvlset.group(name="rank", pass_context=True)
    async def rankset(self, ctx):
        """Rank options."""
        pass

    @lvlset.group(name="levelup", pass_context=True)
    async def levelupset(self, ctx):
        """Level-Up options."""
        pass

    @profileset.command(name="color", alias=["colour"], pass_context=True, no_pm=True)
    async def profilecolors(self, ctx, section: str, color: str):
        """Set profile color.

        For section, you can choose: `exp`, `rep`, `badge`, `info` or `all`.
        For color, you can use: `default`, `white`, `HEX code` (#000000) or `auto`.
        e.g: `[p]lvlset profile color all #eb4034`"""
        user = ctx.author
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_rep = (92, 130, 203, 230)
        default_badge = (128, 151, 165, 230)
        default_exp = (255, 255, 255, 230)
        default_a = 200

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Text-only commands allowed.**")
            return

        # get correct section for db query
        if section == "rep":
            section_name = "rep_color"
        elif section == "exp":
            section_name = "profile_exp_color"
        elif section == "badge":
            section_name = "badge_col_color"
        elif section == "info":
            section_name = "profile_info_color"
        elif section == "all":
            section_name = "all"
        else:
            await ctx.send(
                "**Not a valid section. Must be `rep`, `exp`, `badge`, `info` or `all`.**"
            )
            return

        # get correct color choice
        if color == "auto":
            if not all(lib in globals().keys() for lib in ["numpy", "cluster"]):
                await ctx.send("**Missing required package. Autocolor feature unavailable**")
                return
            if section == "exp":
                color_ranks = [random.randint(2, 3)]
            elif section == "rep":
                color_ranks = [random.randint(2, 3)]
            elif section == "badge":
                color_ranks = [0]  # most prominent color
            elif section == "info":
                color_ranks = [random.randint(0, 1)]
            elif section == "all":
                color_ranks = [
                    random.randint(2, 3),
                    random.randint(2, 3),
                    0,
                    random.randint(0, 2),
                ]

            hex_colors = await self._auto_color(ctx, userinfo["profile_background"], color_ranks)
            set_color = []
            for hex_color in hex_colors:
                color_temp = await self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)

        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "exp":
                set_color = [default_exp]
            elif section == "rep":
                set_color = [default_rep]
            elif section == "badge":
                set_color = [default_badge]
            elif section == "info":
                set_color = [default_info_color]
            elif section == "all":
                set_color = [
                    default_exp,
                    default_rep,
                    default_badge,
                    default_info_color,
                ]
        elif await self._is_hex(color):
            set_color = [await self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send(
                "**Not a valid color. Must be `default`, `HEX color`, `white` or `auto`.**"
            )
            return

        if section == "all":
            if len(set_color) == 1:
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_exp_color": set_color[0],
                            "rep_color": set_color[0],
                            "badge_col_color": set_color[0],
                            "profile_info_color": set_color[0],
                        }
                    },
                )
            elif color == "default":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_exp_color": default_exp,
                            "rep_color": default_rep,
                            "badge_col_color": default_badge,
                            "profile_info_color": default_info_color,
                        }
                    },
                )
            elif color == "auto":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_exp_color": set_color[0],
                            "rep_color": set_color[1],
                            "badge_col_color": set_color[2],
                            "profile_info_color": set_color[3],
                        }
                    },
                )
            await ctx.send("**Colors for profile set.**")
        else:
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {section_name: set_color[0]}}
            )
            await ctx.send("**Color for profile {} set.**".format(section))

    @rankset.command(name="color", alias=["colour"])
    @commands.guild_only()
    async def rankcolors(self, ctx, section: str, color: str = None):
        """Set rank color.

        For section, you can choose: `exp`, `info` or `all`.
        For color, you can use: `default`, `white`, `HEX code` (#000000) or `auto`.
        e.g: `[p]lvlset rank color info white`"""
        user = ctx.author
        server = ctx.guild
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_exp = (255, 255, 255, 230)
        default_rep = (92, 130, 203, 230)
        default_badge = (128, 151, 165, 230)
        default_a = 200

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Text-only commands allowed.**")
            return

        # get correct section for db query
        if section == "exp":
            section_name = "rank_exp_color"
        elif section == "info":
            section_name = "rank_info_color"
        elif section == "all":
            section_name = "all"
        else:
            await ctx.send("**Not a valid section. Must be `exp`, `info` or `all`**")
            return

        # get correct color choice
        if color == "auto":
            if not all(lib in globals().keys() for lib in ["numpy", "cluster"]):
                await ctx.send("**Missing required package. Autocolor feature unavailable**")
                return
            if section == "exp":
                color_ranks = [random.randint(2, 3)]
            elif section == "info":
                color_ranks = [random.randint(0, 1)]
            elif section == "all":
                color_ranks = [random.randint(2, 3), random.randint(0, 1)]

            hex_colors = await self._auto_color(ctx, userinfo["rank_background"], color_ranks)
            set_color = []
            for hex_color in hex_colors:
                color_temp = await self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)
        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "exp":
                set_color = [default_exp]
            elif section == "info":
                set_color = [default_info_color]
            elif section == "all":
                set_color = [
                    default_exp,
                    default_rep,
                    default_badge,
                    default_info_color,
                ]
        elif await self._is_hex(color):
            set_color = [await self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send(
                "**Not a valid color. Must be `default`, `HEX color`, `white or `auto`.**"
            )
            return

        if section == "all":
            if len(set_color) == 1:
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"rank_exp_color": set_color[0], "rank_info_color": set_color[0],}},
                )
            elif color == "default":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "rank_exp_color": default_exp,
                            "rank_info_color": default_info_color,
                        }
                    },
                )
            elif color == "auto":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"rank_exp_color": set_color[0], "rank_info_color": set_color[1],}},
                )
            await ctx.send("**Colors for rank set.**")
        else:
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {section_name: set_color[0]}}
            )
            await ctx.send("**Color for rank {} set.**".format(section))

    @levelupset.command(name="color", alias=["colour"])
    @commands.guild_only()
    async def levelupcolors(self, ctx, section: str, color: str = None):
        """Set levelup color.

        Section can only be `info`.
        Color can be : `default`, `white`, `HEX code` (#000000) or `auto`.
        e.g: `[p]lvlset color info default`"""
        user = ctx.author
        server = ctx.guild
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_a = 200

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Text-only commands allowed.**")
            return

        # get correct section for db query
        if section == "info":
            section_name = "levelup_info_color"
        else:
            await ctx.send("**Not a valid section. Must be `info`.**")
            return

        # get correct color choice
        if color == "auto":
            if not all(lib in globals().keys() for lib in ["numpy", "cluster"]):
                await ctx.send("**Missing required package. Autocolor feature unavailable**")
                return
            if section == "info":
                color_ranks = [random.randint(0, 1)]
            hex_colors = await self._auto_color(ctx, userinfo["levelup_background"], color_ranks)
            set_color = []
            for hex_color in hex_colors:
                color_temp = await self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)
        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "info":
                set_color = [default_info_color]
        elif await self._is_hex(color):
            set_color = [await self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send(
                "**Not a valid color. Must be `default` `HEX color`, `white` or `auto`.**"
            )
            return

        await self.db.users.update_one(
            {"user_id": str(user.id)}, {"$set": {section_name: set_color[0]}}
        )
        await ctx.send("**Color for level-up {} set.**".format(section))

    @profileset.command()
    @commands.guild_only()
    async def info(self, ctx, *, info):
        """Set your user info."""
        user = ctx.author
        max_char = 150

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if len(info) < max_char:
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"info": info}})
            await ctx.send("**Your info section has been succesfully set!**")
        else:
            await ctx.send(
                "**Your description has too many characters! Must be {} or less.**".format(
                    max_char
                )
            )

    @levelupset.command(name="bg")
    @commands.guild_only()
    async def levelbg(self, ctx, *, image_name: str):
        """Set your level-up background."""
        user = ctx.author
        backgrounds = await self.config.backgrounds()

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Text-only commands allowed.**")
            return

        if image_name in backgrounds["levelup"].keys():
            if await self._process_purchase(ctx):
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"levelup_background": backgrounds["levelup"][image_name]}},
                )
                await ctx.send("**Your new level-up background has been succesfully set!**")
        else:
            await ctx.send(
                f"That is not a valid background. See available backgrounds at `{ctx.clean_prefix}backgrounds levelup`."
            )

    @profileset.command(name="bg")
    @commands.guild_only()
    async def profilebg(self, ctx, *, image_name: str):
        """Set your profile background."""
        user = ctx.author
        server = ctx.guild
        backgrounds = await self.config.backgrounds()

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Text-only commands allowed.**")
            return

        if image_name in backgrounds["profile"].keys():
            if await self._process_purchase(ctx):
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"profile_background": backgrounds["profile"][image_name]}},
                )
                await ctx.send("**Your new profile background has been succesfully set!**")
        else:
            await ctx.send(
                f"That is not a valid background. See available backgrounds at `{ctx.clean_prefix}backgrounds profile`."
            )

    @rankset.command(name="bg")
    @commands.guild_only()
    async def rankbg(self, ctx, *, image_name: str):
        """Set your rank background."""
        user = ctx.author
        server = ctx.guild
        backgrounds = await self.config.backgrounds()

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("Leveler commands for this server are disabled.")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Text-only commands allowed.**")
            return

        if image_name in backgrounds["rank"].keys():
            if await self._process_purchase(ctx):
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"rank_background": backgrounds["rank"][image_name]}},
                )
                await ctx.send("**Your new rank background has been succesfully set!**")
        else:
            await ctx.send(
                f"That is not a valid background. See available backgrounds at `{ctx.clean_prefix}backgrounds rank`."
            )

    @profileset.command()
    @commands.guild_only()
    async def title(self, ctx, *, title):
        """Set your title."""
        user = ctx.author
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        max_char = 20

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if len(title) < max_char:
            userinfo["title"] = title
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"title": title}})
            await ctx.send("**Your title has been succesfully set!**")
        else:
            await ctx.send(
                "**Your title has too many characters! Must be {} or less.**".format(max_char)
            )

    @lvlset.group(autohelp=True)
    async def badge(self, ctx):
        """Badge Configuration Options."""
        pass

    @badge.command(name="available")
    @commands.guild_only()
    async def available(self, ctx, badge_type: str = "server"):
        """Get a list of available badges.

        Options: `server` or `global`.
        Defaults for server."""
        server = ctx.guild
        if any([badge_type.casefold() == btype for btype in ["server", "guild"]]):
            servername = server.name
            icon_url = server.icon_url
            serverid = server.id
        elif badge_type.casefold() == "global":
            servername = "Global"
            icon_url = self.bot.user.avatar_url
            serverid = "global"
        else:
            await ctx.send("**Invalid Badge Type. Must be `server` or `global`.**")
            return
        em = discord.Embed(title="Badges available", colour=await ctx.embed_color())
        em.set_author(name="{}".format(servername), icon_url=icon_url)
        msg = ""
        server_badge_info = await self.db.badges.find_one({"server_id": str(serverid)})
        if server_badge_info and server_badge_info["badges"]:
            server_badges = server_badge_info["badges"]
            for badgename in server_badges:
                badgeinfo = server_badges[badgename]
                if badgeinfo["price"] == -1:
                    price = "Non-purchasable"
                elif badgeinfo["price"] == 0:
                    price = "Free"
                else:
                    price = badgeinfo["price"]

                msg += "**• {}** ({}) - {}\n".format(badgename, price, badgeinfo["description"])
        else:
            msg = "None"

        pages = [
            discord.Embed(
                title="Badges available", description=page, colour=await ctx.embed_color(),
            )
            for page in chat.pagify(msg, page_length=2048)
        ]
        pagenum = 1
        for page in pages:
            page.set_author(name=servername, icon_url=icon_url)
            page.set_footer(text="Page {}/{}".format(pagenum, len(pages)))
            pagenum += 1
        await menu(ctx, pages, DEFAULT_CONTROLS)

    @badge.command(name="list")
    @commands.guild_only()
    async def listuserbadges(self, ctx, user: discord.Member = None):
        """Get all badges of a user."""
        if user is None:
            user = ctx.author
        if user.bot:
            await ctx.send_help()
            return
        server = ctx.guild
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        # sort
        priority_badges = []
        for badgename in userinfo["badges"].keys():
            badge = userinfo["badges"][badgename]
            priority_num = badge["priority_num"]
            if priority_num != -1:
                priority_badges.append((badge, priority_num))
        sorted_badges = sorted(priority_badges, key=operator.itemgetter(1), reverse=True)

        badge_ranks = ""
        counter = 1
        for badge, priority_num in sorted_badges[:12]:
            badge_ranks += "**{}. {}** ({}) [{}] **—** {}\n".format(
                counter,
                badge["badge_name"],
                badge["server_name"],
                priority_num,
                badge["description"],
            )
            counter += 1
        if not badge_ranks:
            badge_ranks = "None"

        em = discord.Embed(colour=user.colour)

        total_pages = len(list(chat.pagify(badge_ranks)))
        embeds = []

        counter = 1
        for page in chat.pagify(badge_ranks, ["\n"]):
            em.description = page
            em.set_author(name="Badges for {}".format(user.name), icon_url=user.avatar_url)
            em.set_footer(text="Page {} of {}".format(counter, total_pages))
            embeds.append(em)
            counter += 1
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @badge.command(name="buy")
    @commands.guild_only()
    async def buy(self, ctx, name: str, global_badge: str = None):
        """Buy a badge.

        Option: `-global`."""
        user = ctx.author
        server = ctx.guild
        if global_badge == "-global":
            serverid = "global"
        else:
            serverid = server.id
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)
        server_badge_info = await self.db.badges.find_one({"server_id": str(serverid)})

        if server_badge_info:
            server_badges = server_badge_info["badges"]
            if name in server_badges:

                if "{}_{}".format(name, str(serverid)) not in userinfo["badges"].keys():
                    badge_info = server_badges[name]
                    if badge_info["price"] == -1:
                        await ctx.send("**That badge is not purchasable.**".format(name))
                    elif badge_info["price"] == 0:
                        userinfo["badges"]["{}_{}".format(name, str(serverid))] = server_badges[
                            name
                        ]
                        await self.db.users.update_one(
                            {"user_id": userinfo["user_id"]},
                            {"$set": {"badges": userinfo["badges"]}},
                        )
                        await ctx.send("**`{}` has been obtained.**".format(name))
                    else:
                        await ctx.send(
                            "**{}, you are about to buy the `{}` badge for `{}`. Confirm by typing `yes`.**".format(
                                await self._is_mention(user), name, badge_info["price"]
                            )
                        )
                        pred = MessagePredicate.yes_or_no(ctx)
                        try:
                            await self.bot.wait_for("message", timeout=15, check=pred)
                        except AsyncTimeoutError:
                            pass
                        if not pred.result:
                            await ctx.send("**Purchase canceled.**")
                            return
                        if badge_info["price"] <= await bank.get_balance(user):
                            await bank.withdraw_credits(user, badge_info["price"])
                            userinfo["badges"][
                                "{}_{}".format(name, str(serverid))
                            ] = server_badges[name]
                            await self.db.users.update_one(
                                {"user_id": userinfo["user_id"]},
                                {"$set": {"badges": userinfo["badges"]}},
                            )
                            await ctx.send(
                                "**You have bought the `{}` badge for `{}`.**".format(
                                    name, badge_info["price"]
                                )
                            )
                        elif await bank.get_balance(user) < badge_info["price"]:
                            await ctx.send(
                                "**Not enough money! Need `{}` more.**".format(
                                    badge_info["price"] - await bank.get_balance(user)
                                )
                            )
                else:
                    await ctx.send("**{}, you already have this badge!**".format(user.name))
            else:
                await ctx.send(
                    "**The badge `{}` does not exist. Try `{}badge available`**".format(
                        name, ctx.clean_prefix
                    )
                )
        else:
            await ctx.send(
                "**There are no badges to get! Try `{}badge get [badge name] -global`.**".format(
                    ctx.clean_prefix
                )
            )

    @badge.command(name="set")
    @commands.guild_only()
    async def set_badge(self, ctx, name: str, priority_num: int):
        """Set a badge to profile.

        Options for priority number :
        `-1`: The badge will be invisible.
        `0`: The badge won't be show on your profile.
        Maximum to `5000`."""
        user = ctx.author
        server = ctx.guild

        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if priority_num < -1 or priority_num > 5000:
            await ctx.send("**Invalid priority number! -1-5000**")
            return

        for badge in userinfo["badges"]:
            if userinfo["badges"][badge]["badge_name"] == name:
                userinfo["badges"][badge]["priority_num"] = priority_num
                await self.db.users.update_one(
                    {"user_id": userinfo["user_id"]}, {"$set": {"badges": userinfo["badges"]}},
                )
                await ctx.send(
                    "**The `{}` badge priority has been set to `{}`!**".format(
                        userinfo["badges"][badge]["badge_name"], priority_num
                    )
                )
                break
        else:
            await ctx.send("**You don't have that badge!**")

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="add")
    @commands.guild_only()
    async def addbadge(
        self, ctx, name: str, bg_img: str, border_color: str, price: int, *, description: str,
    ):
        """Add a badge.

        Options :
        `name`: Indicate badge's name. If the badge has space, use quote.
        `bg_img`: Indicate the image of the badge. (Only URL supported)
        `border_color`: Indicate color of the badge's border. (HEX color)
        `price`: Indicate the badge's price. (Indicate `-1` and it won't be purchasable, `0` for free.)
        `description`: Indicate a description for your badge.
        eg: `[p]lvlset badge add Leveler [my_url] #b60047 0 My super badge!`

        If you are the bot owner, you can `-global` to the description to make the badge available everywhere."""

        user = ctx.author
        server = ctx.guild

        # check members
        required_members = 35
        members = len([member for member in server.members if not member.bot])

        if await self.bot.is_owner(user):
            pass
        elif members < required_members:
            await ctx.send(
                "**You may only add badges in servers with {}+ non-bot members**".format(
                    required_members
                )
            )
            return

        if "-global" in description and await self.bot.is_owner(user):
            description = description.replace("-global", "")
            serverid = "global"
            servername = "global"
        else:
            serverid = server.id
            servername = server.name

        if "." in name:
            await ctx.send("**Name cannot contain `.`**")
            return

        if not await self._valid_image_url(bg_img):
            await ctx.send("**Background is not valid. Enter HEX color or image URL!**")
            return

        if not await self._is_hex(border_color):
            await ctx.send("**Border color is not valid!**")
            return

        if price < -1:
            await ctx.send("**Price is not valid!**")
            return

        if len(description.split(" ")) > 40:
            await ctx.send("**Description is too long! Must be 40 or less.**")
            return

        badges = await self.db.badges.find_one({"server_id": str(serverid)})
        if not badges:
            await self.db.badges.insert_one({"server_id": str(serverid), "badges": {}})
            badges = await self.db.badges.find_one({"server_id": str(serverid)})

        new_badge = {
            "badge_name": name,
            "bg_img": bg_img,
            "price": price,
            "description": description,
            "border_color": border_color,
            "server_id": str(serverid),
            "server_name": servername,
            "priority_num": 0,
        }

        if name not in badges["badges"].keys():
            # create the badge regardless
            badges["badges"][name] = new_badge
            await self.db.badges.update_one(
                {"server_id": str(serverid)}, {"$set": {"badges": badges["badges"]}}
            )
            await ctx.send("**`{}` Badge added in `{}` server.**".format(name, servername))
        else:
            # update badge in the server
            badges["badges"][name] = new_badge
            await self.db.badges.update_one(
                {"server_id": serverid}, {"$set": {"badges": badges["badges"]}}
            )

            # go though all users and update the badge.
            # Doing it this way because dynamic does more accesses when doing profile
            async for user in self.db.users.find({}):
                try:
                    user = await self._badge_convert_dict(user)
                    userbadges = user["badges"]
                    badge_name = "{}_{}".format(name, serverid)
                    if badge_name in userbadges.keys():
                        user_priority_num = userbadges[badge_name]["priority_num"]
                        new_badge[
                            "priority_num"
                        ] = user_priority_num  # maintain old priority number set by user
                        userbadges[badge_name] = new_badge
                        await self.db.users.update_one(
                            {"user_id": user["user_id"]}, {"$set": {"badges": userbadges}},
                        )
                except Exception as exc:
                    self.log.error(f"Unable to update badge {name} for {user['user_id']}: {exc}")
            await ctx.send("**The `{}` badge has been updated**".format(name))

    @checks.is_owner()
    @badge.command()
    @commands.guild_only()
    async def type(self, ctx, name: str):
        """Define if badge must be circles or bars."""
        valid_types = ["circles", "bars"]
        if name.lower() not in valid_types:
            await ctx.send("**That is not a valid badge type!**")
            return

        await self.config.badge_type.set(name.lower())
        await ctx.send("**Badge type set to `{}`**".format(name.lower()))

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="delete")
    @commands.guild_only()
    async def delbadge(self, ctx, *, name: str):
        """Delete a badge and remove from all users.

        Option : `-global`."""
        user = ctx.author
        server = ctx.guild

        # return

        if "-global" in name and await self.bot.is_owner(user):
            name = name.replace(" -global", "")
            serverid = "global"
        else:
            serverid = server.id

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        serverbadges = await self.db.badges.find_one({"server_id": str(serverid)})
        if name in serverbadges["badges"].keys():
            del serverbadges["badges"][name]
            await self.db.badges.update_one(
                {"server_id": serverbadges["server_id"]},
                {"$set": {"badges": serverbadges["badges"]}},
            )
            # remove the badge if there
            async for user_info_temp in self.db.users.find({}):
                try:
                    user_info_temp = await self._badge_convert_dict(user_info_temp)

                    badge_name = "{}_{}".format(name, serverid)
                    if badge_name in user_info_temp["badges"].keys():
                        del user_info_temp["badges"][badge_name]
                        await self.db.users.update_one(
                            {"user_id": user_info_temp["user_id"]},
                            {"$set": {"badges": user_info_temp["badges"]}},
                        )
                except Exception as exc:
                    self.log.error(
                        f"Unable to delete badge {name} from {user_info_temp['user_id']}: {exc}"
                    )

            await ctx.send("**The `{}` badge has been removed.**".format(name))
        else:
            await ctx.send("**That badge does not exist.**")

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command()
    @commands.guild_only()
    async def give(self, ctx, user: discord.Member, name: str):
        """Give a user a badge with a certain name
        
        Indicate the user and the badge's name."""
        org_user = ctx.message.author
        server = ctx.guild
        # creates user if doesn't exist
        if user.bot:
            await ctx.send_help()
            return
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        serverbadges = await self.db.badges.find_one({"server_id": str(server.id)})
        badges = serverbadges["badges"]
        badge_name = "{}_{}".format(name, server.id)

        if name not in badges:
            await ctx.send("**That badge doesn't exist in this server!**")
            return
        if badge_name in badges.keys():
            await ctx.send("**{} already has that badge!**".format(await self._is_mention(user)))
            return
        userinfo["badges"][badge_name] = badges[name]
        await self.db.users.update_one(
            {"user_id": str(user.id)}, {"$set": {"badges": userinfo["badges"]}}
        )
        await ctx.send(
            "**{} has just given `{}` the `{}` badge!**".format(
                await self._is_mention(org_user), await self._is_mention(user), name
            )
        )

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command()
    @commands.guild_only()
    async def take(self, ctx, user: discord.Member, name: str):
        """Take a user's badge.

        Indicate the user and the badge's name."""
        if user.bot:
            await ctx.send_help()
            return
        org_user = ctx.author
        server = ctx.guild
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        serverbadges = await self.db.badges.find_one({"server_id": str(server.id)})
        badges = serverbadges["badges"]
        badge_name = "{}_{}".format(name, server.id)

        if name not in badges:
            await ctx.send("**That badge doesn't exist in this server!**")
        elif badge_name not in userinfo["badges"]:
            await ctx.send("**{} does not have that badge!**".format(await self._is_mention(user)))
        else:
            if userinfo["badges"][badge_name]["price"] == -1:
                del userinfo["badges"][badge_name]
                await self.db.users.update_one(
                    {"user_id": str(user.id)}, {"$set": {"badges": userinfo["badges"]}}
                )
                await ctx.send(
                    "**{} has taken the `{}` badge from {}! :upside_down:**".format(
                        await self._is_mention(org_user), name, await self._is_mention(user),
                    )
                )
            else:
                await ctx.send("**You can't take away purchasable badges!**")

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="link")
    @commands.guild_only()
    async def linkbadge(self, ctx, badge_name: str, level: int):
        """Associate a badge with a level.

        Indicate the badge's name and the level."""
        server = ctx.guild
        serverbadges = await self.db.badges.find_one({"server_id": str(server.id)})

        if serverbadges is None:
            await ctx.send("**This server does not have any badges!**")
            return

        if badge_name not in serverbadges["badges"].keys():
            await ctx.send("**Please make sure the `{}` badge exists!**".format(badge_name))
            return
        server_linked_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})
        if not server_linked_badges:
            new_server = {
                "server_id": str(server.id),
                "badges": {badge_name: str(level)},
            }
            await self.db.badgelinks.insert_one(new_server)
        else:
            server_linked_badges["badges"][badge_name] = str(level)
            await self.db.badgelinks.update_one(
                {"server_id": str(server.id)},
                {"$set": {"badges": server_linked_badges["badges"]}},
            )
        await ctx.send(
            "**The `{}` badge has been linked to level `{}`**".format(badge_name, level)
        )

    @checks.admin_or_permissions(manage_roles=True)
    @badge.command(name="unlink")
    @commands.guild_only()
    async def unlinkbadge(self, ctx, badge_name: str):
        """Delete a badge/level association."""
        server = ctx.guild

        server_linked_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})
        badge_links = server_linked_badges["badges"]

        if badge_name in badge_links.keys():
            await ctx.send(
                "**Badge/Level association `{}`/`{}` removed.**".format(
                    badge_name, badge_links[badge_name]
                )
            )
            del badge_links[badge_name]
            await self.db.badgelinks.update_one(
                {"server_id": str(server.id)}, {"$set": {"badges": badge_links}}
            )
        else:
            await ctx.send("**The `{}` badge is not linked to any levels!**".format(badge_name))

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="listlinks")
    @commands.guild_only()
    async def listbadge(self, ctx):
        """List level/badge associations."""
        server = ctx.guild

        server_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})

        if server_badges is None or not server_badges.get("badges"):
            msg = "None"
        else:
            sortorder = sorted(
                server_badges["badges"], key=lambda b: int(server_badges["badges"][b])
            )
            badges = OrderedDict(server_badges["badges"])
            for k in sortorder:
                badges.move_to_end(k)
            msg = "**Badge** → Level\n"
            for badge in badges.keys():
                msg += "**• {} →** {}\n".format(badge, badges[badge])

        pages = list(chat.pagify(msg, page_length=2048))
        embeds = []
        for i, page in enumerate(pages, start=1):
            em = discord.Embed(colour=await ctx.embed_color())
            em.set_author(
                name="Current Badge - Level Links for {}".format(server.name),
                icon_url=server.icon_url,
            )
            em.set_footer(text=f"Page {i}/{len(pages)}")
            em.description = msg
            embeds.append(em)
        await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.command(name="backgrounds", usage="<type>")
    @commands.guild_only()
    async def disp_backgrounds(self, ctx, bg_type: str):
        """Gives a list of backgrounds.

        type can be: `profile`, `rank` or `levelup`."""
        server = ctx.guild
        backgrounds = await self.config.backgrounds()

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        em = discord.Embed(colour=await ctx.embed_color())
        if bg_type.lower() == "profile":
            em.set_author(
                name="Profile Backgrounds for {}".format(self.bot.user.name),
                icon_url=self.bot.user.avatar_url,
            )
            bg_key = "profile"
        elif bg_type.lower() == "rank":
            em.set_author(
                name="Rank Backgrounds for {}".format(self.bot.user.name),
                icon_url=self.bot.user.avatar_url,
            )
            bg_key = "rank"
        elif bg_type.lower() == "levelup":
            em.set_author(
                name="Level Up Backgrounds for {}".format(self.bot.user.name),
                icon_url=self.bot.user.avatar_url,
            )
            bg_key = "levelup"
        else:
            bg_key = None

        if bg_key:
            embeds = []
            total = len(backgrounds[bg_key])
            cnt = 1
            for bg in sorted(backgrounds[bg_key].keys()):
                em = discord.Embed(
                    title=bg,
                    color=await ctx.embed_color(),
                    url=backgrounds[bg_key][bg],
                    description=f"Background {cnt}/{total}",
                )
                em.set_image(url=backgrounds[bg_key][bg])
                embeds.append(em)
                cnt += 1
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send("**Invalid background type. Must be `profile`, `rank` or `levelup`.**")
