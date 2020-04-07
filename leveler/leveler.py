import logging
import math
import operator
import platform
import random
import re
import textwrap
import time
from asyncio import TimeoutError as AsyncTimeoutError
from asyncio import sleep
from collections import OrderedDict
from datetime import timedelta
from io import BytesIO
from typing import Union

import aiohttp
import discord
from discord.utils import find
from fontTools.ttLib import TTFont
from redbot.core import bank
from redbot.core import checks
from redbot.core import commands
from redbot.core.data_manager import bundled_data_path
from redbot.core.utils.chat_formatting import pagify, box
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core.utils.predicates import MessagePredicate

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except Exception as e:
    raise RuntimeError(
        f"Can't load pymongo/motor:{e}\nInstall 'pymongo' and 'motor' packages"
    )
try:
    import scipy
except Exception as e:
    print(
        f"{__file__}: scipy is unable to import: {e}\nAutocolor feature will be unavailable"
    )
try:
    from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageOps, ImageFilter
    from PIL import features as pil_features
except Exception as e:
    raise RuntimeError(f"Can't load pillow: {e}\nDo '[p] pipinstall pillow'.")

from redbot.core import Config

try:
    client = AsyncIOMotorClient()
    db = client["leveler"]
except Exception as e:
    raise RuntimeError(
        f"Can't load database: {e}\nFollow instructions on Git/online to install MongoDB."
    )

log = logging.getLogger("red.fixator10-cogs.leveler")


AVATAR_FORMAT = "webp" if pil_features.check("webp_anim") else "jpg"
log.debug(f"using {AVATAR_FORMAT} avatar format")


# noinspection PyUnusedLocal
async def non_global_bank(ctx):
    return not await bank.is_global()


class Leveler(commands.Cog):
    """A level up thing with image generation!"""

    __version__ = "2.0.8b"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        # fonts
        self.font_file = f"{bundled_data_path(self)}/font.ttf"
        self.font_bold_file = f"{bundled_data_path(self)}/font_bold.ttf"
        self.font_unicode_file = f"{bundled_data_path(self)}/unicode.ttf"
        self.config = Config.get_conf(
            self, identifier=0x3AAFD05EA4AA4FDF8DDEAD8224328191
        )
        default_global = {
            "bg_price": 0,
            "badge_type": "circles",
            "xp": [15, 20],
            "message_length": 10,
            "mention": True,
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
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def cog_unload(self):
        self.session.detach()

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="profile")
    @commands.guild_only()
    async def profile(self, ctx, *, user: discord.Member = None):
        """Displays a user profile."""
        if user is None:
            user = ctx.message.author
        if user.bot:
            ctx.command.reset_cooldown(ctx)
            await ctx.send_help()
            return
        channel = ctx.message.channel
        server = user.guild
        curr_time = time.time()

        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})

        # check if disabled
        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        # no cooldown for text only
        if await self.config.guild(ctx.guild).text_only():
            em = await self.profile_text(user, server, userinfo)
            await channel.send(embed=em)
        else:
            async with ctx.channel.typing():
                profile = await self.draw_profile(user, server)
                file = discord.File(profile, filename="profile.png")
                await channel.send(
                    "**User profile for {}**".format(await self._is_mention(user)),
                    file=file,
                )
            await db.users.update_one(
                {"user_id": str(user.id)},
                {"$set": {"profile_block": curr_time}},
                upsert=True,
            )

    async def profile_text(self, user, server, userinfo):

        em = discord.Embed(colour=user.colour)
        em.add_field(name="Title:", value=userinfo["title"] or None)
        em.add_field(name="Reps:", value=userinfo["rep"])
        em.add_field(
            name="Global Rank:", value="#{}".format(await self._find_global_rank(user))
        )
        em.add_field(
            name="Server Rank:",
            value="#{}".format(await self._find_server_rank(user, server)),
        )
        em.add_field(
            name="Server Level:",
            value=format(userinfo["servers"][str(server.id)]["level"]),
        )
        em.add_field(name="Total Exp:", value=userinfo["total_exp"])
        em.add_field(
            name="Server Exp:", value=await self._find_server_exp(user, server)
        )
        u_credits = await bank.get_balance(user)
        em.add_field(
            name="Credits:",
            value=f"{u_credits}{(await bank.get_currency_name(server))[0]}",
        )
        em.add_field(name="Info:", value=userinfo["info"] or None)
        em.add_field(
            name="Badges:",
            value=(", ".join(userinfo["badges"]).replace("_", " ") or None),
        )
        em.set_author(name="Profile for {}".format(user.name), url=user.avatar_url)
        em.set_thumbnail(url=user.avatar_url)
        return em

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command()
    @commands.guild_only()
    async def rank(self, ctx, *, user: discord.Member = None):
        """Displays the rank of a user."""
        if user is None:
            user = ctx.message.author
        if user.bot:
            ctx.command.reset_cooldown(ctx)
            await ctx.send_help()
            return
        channel = ctx.message.channel
        server = user.guild
        curr_time = time.time()

        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})

        # check if disabled
        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        # no cooldown for text only
        if await self.config.guild(server).text_only():
            em = await self.rank_text(user, server, userinfo)
            await channel.send(embed=em)
        else:
            async with channel.typing():
                rank = await self.draw_rank(user, server)
                file = discord.File(rank, filename="rank.png")
                await channel.send(
                    "**Ranking & Statistics for {}**".format(
                        await self._is_mention(user)
                    ),
                    file=file,
                )
            await db.users.update_one(
                {"user_id": str(user.id)},
                {"$set": {"rank_block".format(server.id): curr_time}},
                upsert=True,
            )

    async def rank_text(self, user, server, userinfo):
        em = discord.Embed(colour=user.colour)
        em.add_field(
            name="Server Rank",
            value="#{}".format(await self._find_server_rank(user, server)),
        )
        em.add_field(name="Reps", value=userinfo["rep"])
        em.add_field(
            name="Server Level", value=userinfo["servers"][str(server.id)]["level"]
        )
        em.add_field(name="Server Exp", value=await self._find_server_exp(user, server))
        em.set_author(
            name="Rank & Statistics for {}".format(user.name), url=user.avatar_url
        )
        em.set_thumbnail(url=user.avatar_url)
        return em

    # should the user be mentioned based on settings?
    async def _is_mention(self, user):
        if await self.config.mention():
            return user.mention
        return user.name

    @commands.command(usage="[page] [-rep] [-global]")
    @commands.guild_only()
    async def top(self, ctx, *options):
        """Displays leaderboard.

        Add -global parameter for global and -rep for reputation."""
        server = ctx.guild
        user = ctx.author

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        async with ctx.typing():
            users = []
            user_stat = None
            if "-rep" in options and "-global" in options:
                title = "Global Rep Leaderboard for {}\n".format(self.bot.user.name)
                async for userinfo in db.users.find({}):
                    try:
                        users.append((userinfo["username"], userinfo["rep"]))
                    except KeyError:
                        users.append((userinfo["user_id"], userinfo["rep"]))

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = userinfo["rep"]

                board_type = "Rep"
                footer_text = "Your Rank: {}                  {}: {}".format(
                    await self._find_global_rep_rank(user), board_type, user_stat
                )
                icon_url = self.bot.user.avatar_url
            elif "-global" in options:
                title = "Global Exp Leaderboard for {}\n".format(self.bot.user.name)
                async for userinfo in db.users.find({}):
                    try:
                        users.append((userinfo["username"], userinfo["total_exp"]))
                    except KeyError:
                        users.append((userinfo["user_id"], userinfo["total_exp"]))

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = userinfo["total_exp"]

                board_type = "Points"
                footer_text = "Your Rank: {}                  {}: {}".format(
                    await self._find_global_rank(user), board_type, user_stat
                )
                icon_url = self.bot.user.avatar_url
            elif "-rep" in options:
                title = "Rep Leaderboard for {}\n".format(server.name)
                async for userinfo in db.users.find({}):
                    if "servers" in userinfo and str(server.id) in userinfo["servers"]:
                        try:
                            users.append((userinfo["username"], userinfo["rep"]))
                        except KeyError:
                            users.append((userinfo["user_id"], userinfo["rep"]))

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = userinfo["rep"]

                board_type = "Rep"
                footer_text = "Your Rank: {}                  {}: {}".format(
                    await self._find_server_rep_rank(user, server),
                    board_type,
                    user_stat,
                )
                icon_url = server.icon_url
            else:
                title = "Exp Leaderboard for {}\n".format(server.name)
                async for userinfo in db.users.find({}):
                    try:
                        if (
                            "servers" in userinfo
                            and str(server.id) in userinfo["servers"]
                        ):
                            server_exp = 0
                            for i in range(
                                userinfo["servers"][str(server.id)]["level"]
                            ):
                                server_exp += await self._required_exp(i)
                            server_exp += userinfo["servers"][str(server.id)][
                                "current_exp"
                            ]
                            try:
                                users.append((userinfo["username"], server_exp))
                            except KeyError:
                                users.append((userinfo["user_id"], server_exp))
                    except KeyError:
                        pass
                board_type = "Points"
                footer_text = "Your Rank: {}                  {}: {}".format(
                    await self._find_server_rank(user, server),
                    board_type,
                    await self._find_server_exp(user, server),
                )
                icon_url = server.icon_url
            sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

            # multiple page support
            page = 1
            per_page = 15
            pages = math.ceil(len(sorted_list) / per_page)
            for option in options:
                if str(option).isdigit():
                    if page >= 1 and int(option) <= pages:
                        page = int(str(option))
                    else:
                        await ctx.send(
                            "**Please enter a valid page number! (1 - {})**".format(
                                str(pages)
                            )
                        )
                        return
                    break

            msg = ""
            msg += "Rank     Name                   (Page {}/{})     \n\n".format(
                page, pages
            )
            rank = 1 + per_page * (page - 1)
            start_index = per_page * page - per_page
            end_index = per_page * page

            default_label = "   "
            special_labels = ["♔", "♕", "♖", "♗", "♘", "♙"]

            async for single_user in self.asyncit(sorted_list[start_index:end_index]):
                if rank - 1 < len(special_labels):
                    label = special_labels[rank - 1]
                else:
                    label = default_label

                msg += "{:<2}{:<2}{:<2} # {:<11}".format(
                    rank, label, "➤", await self._truncate_text(single_user[0], 11)
                )
                msg += "{:>5}{:<2}{:<2}{:<5}\n".format(
                    " ", " ", " ", " {}: ".format(board_type) + str(single_user[1])
                )
                rank += 1
            msg += "--------------------------------------------            \n"
            msg += "{}".format(footer_text)

            em = discord.Embed(description="", colour=user.colour)
            em.set_author(name=title, icon_url=icon_url)
            em.description = box(msg)

        await ctx.send(embed=em)

    @commands.command()
    @commands.guild_only()
    async def rep(self, ctx, *, user: discord.Member = None):
        """Gives a reputation point to a designated player."""
        org_user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(org_user, server)
        if user:
            await self._create_user(user, server)
        org_userinfo = await db.users.find_one({"user_id": str(org_user.id)})
        curr_time = time.time()

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return
        if user and user.id == org_user.id:
            await ctx.send("**You can't give a rep to yourself!**")
            return
        if user and user.bot:
            await ctx.send("**You can't give a rep to a bot!**")
            return
        if "rep_block" not in org_userinfo:
            org_userinfo["rep_block"] = 0

        delta = float(curr_time) - float(org_userinfo["rep_block"])
        if user and delta >= 43200.0 and delta > 0:
            userinfo = await db.users.find_one({"user_id": str(user.id)})
            await db.users.update_one(
                {"user_id": str(org_user.id)}, {"$set": {"rep_block": curr_time}}
            )
            await db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"rep": userinfo["rep"] + 1}}
            )
            await ctx.send(
                "**You have just given {} a reputation point!**".format(
                    await self._is_mention(user)
                )
            )
        else:
            # calulate time left
            seconds = 43200 - delta
            if seconds < 0:
                await ctx.send("**You can give a rep!**")
                return

            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            await ctx.send(
                "**You need to wait {} hours, {} minutes, and {} seconds until you can give reputation again!**".format(
                    int(h), int(m), int(s)
                )
            )

    @commands.command()
    @commands.guild_only()
    async def lvlinfo(self, ctx, *, user: discord.Member = None):
        """Gives more specific details about user profile image."""
        if not user:
            user = ctx.author
        if user.bot:
            await ctx.send_help()
            return
        server = ctx.guild
        userinfo = await db.users.find_one({"user_id": str(user.id)})

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        # creates user if doesn't exist
        await self._create_user(user, server)
        msg = ""
        msg += "Name: {}\n".format(user.name)
        msg += "Title: {}\n".format(userinfo["title"])
        msg += "Reps: {}\n".format(userinfo["rep"])
        msg += "Server Level: {}\n".format(userinfo["servers"][str(server.id)]["level"])
        total_server_exp = 0
        for i in range(userinfo["servers"][str(server.id)]["level"]):
            total_server_exp += await self._required_exp(i)
        total_server_exp += userinfo["servers"][str(server.id)]["current_exp"]
        msg += "Server Exp: {}\n".format(total_server_exp)
        msg += "Total Exp: {}\n".format(userinfo["total_exp"])
        msg += "Info: {}\n".format(userinfo["info"])
        msg += "Profile background: {}\n".format(userinfo["profile_background"])
        msg += "Rank background: {}\n".format(userinfo["rank_background"])
        msg += "Levelup background: {}\n".format(userinfo["levelup_background"])
        if "profile_info_color" in userinfo.keys() and userinfo["profile_info_color"]:
            msg += "Profile info color: {}\n".format(
                self._rgb_to_hex(userinfo["profile_info_color"])
            )
        if "profile_exp_color" in userinfo.keys() and userinfo["profile_exp_color"]:
            msg += "Profile exp color: {}\n".format(
                self._rgb_to_hex(userinfo["profile_exp_color"])
            )
        if "rep_color" in userinfo.keys() and userinfo["rep_color"]:
            msg += "Rep section color: {}\n".format(
                self._rgb_to_hex(userinfo["rep_color"])
            )
        if "badge_col_color" in userinfo.keys() and userinfo["badge_col_color"]:
            msg += "Badge section color: {}\n".format(
                self._rgb_to_hex(userinfo["badge_col_color"])
            )
        if "rank_info_color" in userinfo.keys() and userinfo["rank_info_color"]:
            msg += "Rank info color: {}\n".format(
                self._rgb_to_hex(userinfo["rank_info_color"])
            )
        if "rank_exp_color" in userinfo.keys() and userinfo["rank_exp_color"]:
            msg += "Rank exp color: {}\n".format(
                self._rgb_to_hex(userinfo["rank_exp_color"])
            )
        if "levelup_info_color" in userinfo.keys() and userinfo["levelup_info_color"]:
            msg += "Level info color: {}\n".format(
                self._rgb_to_hex(userinfo["levelup_info_color"])
            )
        msg += "Badges: "
        msg += ", ".join(userinfo["badges"])

        em = discord.Embed(description=msg, colour=user.colour)
        em.set_author(
            name="Profile Information for {}".format(user.name),
            icon_url=user.avatar_url,
        )
        await ctx.send(embed=em)

    def _rgb_to_hex(self, rgb):
        rgb = tuple(rgb[:3])
        return "#%02x%02x%02x" % rgb

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

    @profileset.command(name="color", pass_context=True, no_pm=True)
    async def profilecolors(self, ctx, section: str, color: str):
        """Set profile color.

        For section, you can choose: `exp`, `rep`, `badge`, `info` or `all`.
        For color, you can use: `default`, `white`, `HEX code` (#000000) or `auto`.
        e.g: `[p]lvlset profile color all #eb4034`"""
        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})

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

            hex_colors = await self._auto_color(
                ctx, userinfo["profile_background"], color_ranks
            )
            set_color = []
            for hex_color in hex_colors:
                color_temp = self._hex_to_rgb(hex_color, default_a)
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
        elif self._is_hex(color):
            set_color = [self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send(
                "**Not a valid color. Must be `default`, `HEX color`, `white` or `auto`.**"
            )
            return

        if section == "all":
            if len(set_color) == 1:
                await db.users.update_one(
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
                await db.users.update_one(
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
                await db.users.update_one(
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
            await db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {section_name: set_color[0]}}
            )
            await ctx.send("**Color for profile {} set.**".format(section))

    @rankset.command(name="color")
    @commands.guild_only()
    async def rankcolors(self, ctx, section: str, color: str = None):
        """Set rank color.

        For section, you can choose: `exp`, `info` or `all`.
        For color, you can use: `default`, `white`, `HEX code` (#000000) or `auto`.
        e.g: `[p]lvlset rank color info white`"""
        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})

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
            if section == "exp":
                color_ranks = [random.randint(2, 3)]
            elif section == "info":
                color_ranks = [random.randint(0, 1)]
            elif section == "all":
                color_ranks = [random.randint(2, 3), random.randint(0, 1)]

            hex_colors = await self._auto_color(
                ctx, userinfo["rank_background"], color_ranks
            )
            set_color = []
            for hex_color in hex_colors:
                color_temp = self._hex_to_rgb(hex_color, default_a)
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
        elif self._is_hex(color):
            set_color = [self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send(
                "**Not a valid color. Must be `default`, `HEX color`, `white or `auto`.**"
            )
            return

        if section == "all":
            if len(set_color) == 1:
                await db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "rank_exp_color": set_color[0],
                            "rank_info_color": set_color[0],
                        }
                    },
                )
            elif color == "default":
                await db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "rank_exp_color": default_exp,
                            "rank_info_color": default_info_color,
                        }
                    },
                )
            elif color == "auto":
                await db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "rank_exp_color": set_color[0],
                            "rank_info_color": set_color[1],
                        }
                    },
                )
            await ctx.send("**Colors for rank set.**")
        else:
            await db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {section_name: set_color[0]}}
            )
            await ctx.send("**Color for rank {} set.**".format(section))

    @levelupset.command(name="color")
    @commands.guild_only()
    async def levelupcolors(self, ctx, section: str, color: str = None):
        """Set levelup color.

        Section can only be `info`.
        Color can be : `default`, `white`, `HEX code` (#000000) or `auto`.
        e.g: `[p]lvlset color info default`"""
        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})

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
            if section == "info":
                color_ranks = [random.randint(0, 1)]
            hex_colors = await self._auto_color(
                ctx, userinfo["levelup_background"], color_ranks
            )
            set_color = []
            for hex_color in hex_colors:
                color_temp = self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)
        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "info":
                set_color = [default_info_color]
        elif self._is_hex(color):
            set_color = [self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send("**Not a valid color. Must be `default` `HEX color`, `white` or `auto`.**")
            return

        await db.users.update_one(
            {"user_id": str(user.id)}, {"$set": {section_name: set_color[0]}}
        )
        await ctx.send("**Color for level-up {} set.**".format(section))

    # uses k-means algorithm to find color from bg, rank is abundance of color, descending
    async def _auto_color(self, ctx, url: str, ranks):
        if "scipy" not in globals():
            await ctx.send("**Bot missing a required package. Cannot use Autocolor feature.**")
            return
        phrases = ["Calculating colors..."]  # in case I want more
        await ctx.send("**{}**".format(random.choice(phrases)))
        clusters = 10

        async with self.session.get(url) as r:
            image = await r.content.read()
        image = BytesIO(image)

        im = Image.open(image).convert("RGBA")
        im = im.resize((290, 290))  # resized to reduce time
        ar = scipy.asarray(im)
        shape = ar.shape
        ar = ar.reshape(scipy.product(shape[:2]), shape[2])

        codes, dist = scipy.cluster.vq.kmeans(ar.astype(float), clusters)
        vecs, dist = scipy.cluster.vq.vq(ar, codes)  # assign codes
        counts, bins = scipy.histogram(vecs, len(codes))  # count occurrences

        # sort counts
        freq_index = []
        index = 0
        for count in counts:
            freq_index.append((index, count))
            index += 1
        sorted_list = sorted(freq_index, key=operator.itemgetter(1), reverse=True)

        colors = []
        for rank in ranks:
            color_index = min(rank, len(codes))
            peak = codes[sorted_list[color_index][0]]  # gets the original index
            peak = peak.astype(int)

            colors.append("".join(format(c, "02x") for c in peak))
        return colors  # returns array

    # converts hex to rgb
    def _hex_to_rgb(self, hex_num: str, a: int):
        h = hex_num.lstrip("#")

        # if only 3 characters are given
        if len(str(h)) == 3:
            expand = "".join([x * 2 for x in str(h)])
            h = expand

        colors = [int(h[i : i + 2], 16) for i in (0, 2, 4)]
        colors.append(a)
        return tuple(colors)

    # dampens the color given a parameter
    def _moderate_color(self, rgb, moderate_num):
        new_colors = []
        for color in rgb[:3]:
            if color > 128:
                color -= moderate_num
            else:
                color += moderate_num
            new_colors.append(color)
        new_colors.append(230)

        return tuple(new_colors)

    @profileset.command()
    @commands.guild_only()
    async def info(self, ctx, *, info):
        """Set your user info."""
        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        max_char = 150

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if len(info) < max_char:
            await db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"info": info}}
            )
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
        server = ctx.guild
        backgrounds = await self.config.backgrounds()
        # creates user if doesn't exist
        await self._create_user(user, server)

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Text-only commands allowed.**")
            return

        if image_name in backgrounds["levelup"].keys():
            if await self._process_purchase(ctx):
                await db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "levelup_background": backgrounds["levelup"][image_name]
                        }
                    },
                )
                await ctx.send(
                    "**Your new level-up background has been succesfully set!**"
                )
        else:
            await ctx.send(
                f"That is not a valid background. See available backgrounds at `{ctx.prefix}backgrounds levelup`."
            )

    @profileset.command(name="bg")
    @commands.guild_only()
    async def profilebg(self, ctx, *, image_name: str):
        """Set your profile background."""
        user = ctx.author
        server = ctx.guild
        backgrounds = await self.config.backgrounds()
        # creates user if doesn't exist
        await self._create_user(user, server)

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Text-only commands allowed.**")
            return

        if image_name in backgrounds["profile"].keys():
            if await self._process_purchase(ctx):
                await db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_background": backgrounds["profile"][image_name]
                        }
                    },
                )
                await ctx.send(
                    "**Your new profile background has been succesfully set!**"
                )
        else:
            await ctx.send(
                f"That is not a valid background. See available backgrounds at `{ctx.prefix}backgrounds profile`."
            )

    @rankset.command(name="bg")
    @commands.guild_only()
    async def rankbg(self, ctx, *, image_name: str):
        """Set your rank background."""
        user = ctx.author
        server = ctx.guild
        backgrounds = await self.config.backgrounds()
        # creates user if doesn't exist
        await self._create_user(user, server)

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("Leveler commands for this server are disabled.")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Text-only commands allowed.**")
            return

        if image_name in backgrounds["rank"].keys():
            if await self._process_purchase(ctx):
                await db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"rank_background": backgrounds["rank"][image_name]}},
                )
                await ctx.send("**Your new rank background has been succesfully set!**")
        else:
            await ctx.send(
                f"That is not a valid background. See available backgrounds at `{ctx.prefix}backgrounds rank`."
            )

    @profileset.command()
    @commands.guild_only()
    async def title(self, ctx, *, title):
        """Set your title."""
        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})
        max_char = 20

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if len(title) < max_char:
            userinfo["title"] = title
            await db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"title": title}}
            )
            await ctx.send("**Your title has been succesfully set!**")
        else:
            await ctx.send(
                "**Your title has too many characters! Must be {} or less.**".format(max_char)
            )

    @checks.admin_or_permissions(manage_guild=True)
    @commands.group()
    @commands.guild_only()
    async def lvladmin(self, ctx):
        """Admin options features."""
        pass

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.group()
    async def overview(self, ctx):
        """A list of settings."""

        disabled_servers = []
        private_levels = []
        disabled_levels = []
        locked_channels = []

        for guild in self.bot.guilds:
            if await self.config.guild(guild).disabled():
                disabled_servers.append(guild.name)
            if await self.config.guild(guild).lvl_msg_lock():
                locked_channels.append(
                    "\n{} → #{}".format(
                        guild.name,
                        guild.get_channel(
                            await self.config.guild(guild).lvl_msg_lock()
                        ),
                    )
                )
            if await self.config.guild(guild).lvl_msg():
                disabled_levels.append(guild.name)
            if await self.config.guild(guild).private_lvl_message():
                private_levels.append(guild.name)

        num_users = len(await db.users.find({}).to_list(None))

        msg = ""
        msg += "**Servers:** {}\n".format(len(self.bot.guilds))
        msg += "**Unique Users:** {}\n".format(num_users)
        msg += "**Mentions:** {}\n".format(await self.config.mention())
        msg += "**Background Price:** {}\n".format(await self.config.bg_price())
        msg += "**Badge type:** {}\n".format(await self.config.badge_type())
        msg += "**Disabled Servers:** {}\n".format(", ".join(disabled_servers))
        msg += "**Enabled Level Messages:** {}\n".format(", ".join(disabled_levels))
        msg += "**Private Level Messages:** {}\n".format(", ".join(private_levels))
        msg += "**Channel Locks:** {}\n".format(", ".join(locked_channels))
        em = discord.Embed(description=msg, colour=await ctx.embed_color())
        em.set_author(name="Settings Overview for {}".format(self.bot.user.name))
        await ctx.send(embed=em)

    @lvladmin.command()
    @commands.guild_only()
    @commands.check(non_global_bank)
    async def msgcredits(self, ctx, currency: int = 0):
        """Credits per message logged.

        Default to `0`."""
        server = ctx.guild

        if currency < 0 or currency > 1000:
            await ctx.send("**Please enter a valid number between 0 and 1000.**")
            return

        await self.config.guild(server).msg_credits.set(currency)
        await ctx.send("**Credits per message logged set to `{}`.**".format(currency))

    @lvladmin.command()
    @commands.guild_only()
    async def ignorechannel(self, ctx, channel: discord.TextChannel = None):
        """Blocks exp gain in certain channel.

        Use command without channel to see list of ignored channels."""
        server = ctx.guild
        if channel is None:
            channels = [
                server.get_channel(c) and server.get_channel(c).mention or c
                for c in await self.config.guild(server).ignored_channels()
                if server.get_channel(c)
            ]
            await ctx.send(
                "**Ignored channels:** \n"
                + ("\n".join(channels) or "No ignored channels set")
            )
            return
        if channel.id in await self.config.guild(server).ignored_channels():
            async with self.config.guild(server).ignored_channels() as channels:
                channels.remove(channel.id)
            await ctx.send(f"**Messages in {channel.mention} will give exp now.**")
        else:
            async with self.config.guild(server).ignored_channels() as channels:
                channels.append(channel.id)
            await ctx.send(f"**Messages in {channel.mention} will not give exp now.**")

    @lvladmin.command(name="lock")
    @commands.guild_only()
    async def lvlmsglock(self, ctx):
        """Locks levelup messages to one channel.

        Disable command via locked channel."""
        channel = ctx.channel
        server = ctx.guild

        if channel.id == await self.config.guild(server).lvl_msg_lock():
            await self.config.guild(server).lvl_msg_lock.set(None)
            await ctx.send("**Level-up message lock disabled.**")
        else:
            await self.config.guild(server).lvl_msg_lock.set(channel.id)
            await ctx.send("**Level-up messages locked to `#{}`**".format(channel.name))

    async def _process_purchase(self, ctx):
        user = ctx.author
        server = ctx.guild
        bg_price = await self.config.bg_price()

        if bg_price != 0:
            if not await bank.can_spend(user, bg_price):
                await ctx.send(
                    f"**Insufficient funds. Backgrounds changes cost: "
                    f"{bg_price}{(await bank.get_currency_name(server))[0]}**"
                )
                return False
            await ctx.send(
                "**{}, you are about to buy a background for `{}`. Confirm by typing `yes`.**".format(
                    await self._is_mention(user), bg_price
                )
            )
            pred = MessagePredicate.yes_or_no(ctx)
            try:
                await self.bot.wait_for("message", timeout=15, check=pred)
            except AsyncTimeoutError:
                pass
            if not pred.result:
                await ctx.send("**Purchase canceled.**")
                return False
            await bank.withdraw_credits(user, bg_price)
            return True
        return True

    async def _give_chat_credit(self, user, server):
        msg_credits = await self.config.guild(server).msg_credits()
        if msg_credits and not await bank.is_global():
            await bank.deposit_credits(user, msg_credits)

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def setprice(self, ctx, price: int):
        """Set a price for background changes."""
        if price < 0:
            await ctx.send("**That is not a valid background price.**")
        else:
            await self.config.bg_price.set(price)
            await ctx.send(f"**Background price set to: `{price}`!**")

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def setlevel(self, ctx, user: discord.Member, level: int):
        """Set a user's level. (What a cheater C:)."""
        server = user.guild
        channel = ctx.channel
        # creates user if doesn't exist
        if user.bot:
            await ctx.send_help()
            return
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("Leveler commands for this server are disabled.")
            return

        if level < 0:
            await ctx.send("**Please enter a positive number.**")
            return

        # get rid of old level exp
        old_server_exp = 0
        for i in range(userinfo["servers"][str(server.id)]["level"]):
            old_server_exp += await self._required_exp(i)
        userinfo["total_exp"] -= old_server_exp
        userinfo["total_exp"] -= userinfo["servers"][str(server.id)]["current_exp"]

        # add in new exp
        total_exp = await self._level_exp(level)
        userinfo["servers"][str(server.id)]["current_exp"] = 0
        userinfo["servers"][str(server.id)]["level"] = level
        userinfo["total_exp"] += total_exp

        await db.users.update_one(
            {"user_id": str(user.id)},
            {
                "$set": {
                    "servers.{}.level".format(server.id): level,
                    "servers.{}.current_exp".format(server.id): 0,
                    "total_exp": userinfo["total_exp"],
                }
            },
        )
        await ctx.send(
            "**{}'s Level has been set to `{}`.**".format(
                await self._is_mention(user), level
            )
        )
        await self._handle_levelup(user, userinfo, server, channel)

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def xpban(self, ctx, days: int, *, user: Union[discord.Member, int]):
        """Ban user from getting experience."""
        if isinstance(user, int):
            try:
                user = await self.bot.fetch_user(user)
            except discord.NotFound:
                await ctx.send("Discord user with ID `{}` not found.".format(user))
                return
            except discord.HTTPException:
                await ctx.send("I was unable to get data about user with ID `{}`. Try again later.".format(user))
                return
        if user is None:
            await ctx.send_help()
            return
        chat_block = time.time() + timedelta(days=days).total_seconds()
        try:
            await db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"chat_block": chat_block}}
            )
        except Exception as exc:
            await ctx.send("Unable to add chat block: {}".format(exc))
        else:
            await ctx.tick()

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def mention(self, ctx):
        """Toggle mentions on messages."""
        if await self.config.mention():
            await self.config.mention.set(False)
            await ctx.send("**Mentions disabled.**")
        else:
            await self.config.mention.set(True)
            await ctx.send("**Mentions enabled.**")

    async def _valid_image_url(self, url):

        try:
            async with self.session.get(url) as r:
                image = await r.content.read()
            image = BytesIO(image)
            Image.open(image).convert("RGBA")
            return True
        except IOError:
            return False

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command()
    @commands.guild_only()
    async def toggle(self, ctx):
        """Toggle most leveler commands on the current server."""
        server = ctx.guild
        if await self.config.guild(server).disabled():
            await self.config.guild(server).disabled.set(False)
            await ctx.send("**Leveler enabled on `{}`.**".format(server.name))
        else:
            await self.config.guild(server).disabled.set(True)
            await ctx.send("**Leveler disabled on `{}`.**".format(server.name))

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command()
    @commands.guild_only()
    async def textonly(self, ctx):
        """Toggle text-based messages on the server."""
        server = ctx.guild
        if await self.config.guild(server).text_only():
            await self.config.guild(server).text_only.set(False)
            await ctx.send(
                "**Text-only messages disabled for `{}`.**".format(server.name)
            )
        else:
            await self.config.guild(server).text_only.set(True)
            await ctx.send(
                "**Text-only messages enabled for `{}`.**".format(server.name)
            )

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command(name="alerts")
    @commands.guild_only()
    async def lvlalert(self, ctx):
        """Toggle level-up messages on the server."""
        server = ctx.guild

        if await self.config.guild(server).lvl_msg():
            await self.config.guild(server).lvl_msg.set(False)
            await ctx.send("**Level-up alerts disabled for `{}`.**".format(server.name))
        else:
            await self.config.guild(server).lvl_msg.set(True)
            await ctx.send("**Level-up alerts enabled for `{}`.**".format(server.name))

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command(name="private")
    @commands.guild_only()
    async def lvlprivate(self, ctx):
        """Toggles level-up alert in private message to the user."""
        server = ctx.guild
        if await self.config.guild(server).private_lvl_message():
            await self.config.guild(server).private_lvl_message.set(False)
            await ctx.send(
                "**Private level-up alerts disabled for `{}`.**".format(server.name)
            )
        else:
            await self.config.guild(server).private_lvl_message.set(True)
            await ctx.send(
                "**Private level-up alerts enabled for `{}`.**".format(server.name)
            )

    @lvladmin.command(aliases=["exp"])
    @checks.is_owner()
    async def xp(self, ctx, min_xp: int = 15, max_xp: int = 20):
        """Set the range for the XP given on each successful XP gain.

        Leaving the entries blank will reset the XP to the default (Min: 15 - Max: 20)."""
        if (max_xp or min_xp) > 1000:
            return await ctx.send(
                "Don't you think that number is a bit high? "
                "That might break things. Try something under 1k xp."
            )
        if max_xp == 0:
            return await ctx.send("Max XP can't be zero or less.")
        if min_xp >= max_xp:
            return await ctx.send(
                "The minimum XP amount needs to be less than the maximum XP amount."
            )
        if (min_xp or max_xp) < 0:
            return await ctx.send("The XP amounts can't be less then zero.")
        await self.config.xp.set([min_xp, max_xp])
        await ctx.send(
            f"XP given has been set to a range of {min_xp} to {max_xp} XP per message."
        )

    @lvladmin.command()
    @checks.is_owner()
    async def length(self, ctx, message_length: int = 10):
        """Set minimum message length for XP gain.

        Messages with attachments will give XP regardless of length"""
        if message_length < 0:
            raise commands.BadArgument
        await self.config.message_length.set(message_length)
        await ctx.tick()

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
        server_badge_info = await db.badges.find_one({"server_id": str(serverid)})
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

                msg += "**• {}** ({}) - {}\n".format(
                    badgename, price, badgeinfo["description"]
                )
        else:
            msg = "None"

        pages = [
            discord.Embed(
                title="Badges available",
                description=page,
                colour=await ctx.embed_color(),
            )
            for page in pagify(msg, page_length=2048)
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
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        # sort
        priority_badges = []
        for badgename in userinfo["badges"].keys():
            badge = userinfo["badges"][badgename]
            priority_num = badge["priority_num"]
            if priority_num != -1:
                priority_badges.append((badge, priority_num))
        sorted_badges = sorted(
            priority_badges, key=operator.itemgetter(1), reverse=True
        )

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

        total_pages = len(list(pagify(badge_ranks)))
        embeds = []

        counter = 1
        for page in pagify(badge_ranks, ["\n"]):
            em.description = page
            em.set_author(
                name="Badges for {}".format(user.name), icon_url=user.avatar_url
            )
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
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)
        server_badge_info = await db.badges.find_one({"server_id": str(serverid)})

        if server_badge_info:
            server_badges = server_badge_info["badges"]
            if name in server_badges:

                if "{}_{}".format(name, str(serverid)) not in userinfo["badges"].keys():
                    badge_info = server_badges[name]
                    if badge_info["price"] == -1:
                        await ctx.send(
                            "**That badge is not purchasable.**".format(name)
                        )
                    elif badge_info["price"] == 0:
                        userinfo["badges"][
                            "{}_{}".format(name, str(serverid))
                        ] = server_badges[name]
                        await db.users.update_one(
                            {"user_id": userinfo["user_id"]},
                            {"$set": {"badges": userinfo["badges"]}},
                        )
                        await ctx.send("**`{}` has been obtained.**".format(name))
                    else:
                        await ctx.send(
                            '**{}, you are about to buy the `{}` badge for `{}`. Confirm by typing `yes`.**'.format(
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
                            await db.users.update_one(
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
                    await ctx.send(
                        "**{}, you already have this badge!**".format(user.name)
                    )
            else:
                await ctx.send(
                    "**The badge `{}` does not exist. Try `{}badge available`**".format(
                        name, ctx.prefix
                    )
                )
        else:
            await ctx.send(
                "**There are no badges to get! Try `{}badge get [badge name] -global`.**".format(
                    ctx.prefix
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
        await self._create_user(user, server)

        userinfo = await db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if priority_num < -1 or priority_num > 5000:
            await ctx.send("**Invalid priority number! -1-5000**")
            return

        for badge in userinfo["badges"]:
            if userinfo["badges"][badge]["badge_name"] == name:
                userinfo["badges"][badge]["priority_num"] = priority_num
                await db.users.update_one(
                    {"user_id": userinfo["user_id"]},
                    {"$set": {"badges": userinfo["badges"]}},
                )
                await ctx.send(
                    "**The `{}` badge priority has been set to `{}`!**".format(
                        userinfo["badges"][badge]["badge_name"], priority_num
                    )
                )
                break
        else:
            await ctx.send("**You don't have that badge!**")

    async def _badge_convert_dict(self, userinfo):
        if "badges" not in userinfo or not isinstance(userinfo["badges"], dict):
            await db.users.update_one(
                {"user_id": userinfo["user_id"]}, {"$set": {"badges": {}}}
            )
        return await db.users.find_one({"user_id": userinfo["user_id"]})

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="add")
    @commands.guild_only()
    async def addbadge(
        self,
        ctx,
        name: str,
        bg_img: str,
        border_color: str,
        price: int,
        *,
        description: str,
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

        if not self._is_hex(border_color):
            await ctx.send("**Border color is not valid!**")
            return

        if price < -1:
            await ctx.send("**Price is not valid!**")
            return

        if len(description.split(" ")) > 40:
            await ctx.send("**Description is too long! Must be 40 or less.**")
            return

        badges = await db.badges.find_one({"server_id": str(serverid)})
        if not badges:
            await db.badges.insert_one({"server_id": str(serverid), "badges": {}})
            badges = await db.badges.find_one({"server_id": str(serverid)})

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
            await db.badges.update_one(
                {"server_id": str(serverid)}, {"$set": {"badges": badges["badges"]}}
            )
            await ctx.send(
                "**`{}` Badge added in `{}` server.**".format(name, servername)
            )
        else:
            # update badge in the server
            badges["badges"][name] = new_badge
            await db.badges.update_one(
                {"server_id": serverid}, {"$set": {"badges": badges["badges"]}}
            )

            # go though all users and update the badge.
            # Doing it this way because dynamic does more accesses when doing profile
            async for user in db.users.find({}):
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
                        await db.users.update_one(
                            {"user_id": user["user_id"]},
                            {"$set": {"badges": userbadges}},
                        )
                except Exception as exc:
                    log.error(
                        f"Unable to update badge {name} for {user['user_id']}: {exc}"
                    )
            await ctx.send("**The `{}` badge has been updated**".format(name))

    @checks.is_owner()
    @badge.command()
    @commands.guild_only()
    async def type(self, ctx, name: str):
        """Define if badge must be circle or bars."""
        valid_types = ["circles", "bars"]
        if name.lower() not in valid_types:
            await ctx.send("**That is not a valid badge type!**")
            return

        await self.config.badge_type.set(name.lower())
        await ctx.send("**Badge type set to `{}`**".format(name.lower()))

    def _is_hex(self, color: str):
        if color is not None and len(color) != 4 and len(color) != 7:
            return False

        reg_ex = r"^#(?:[0-9a-fA-F]{3}){1,2}$"
        return re.search(reg_ex, str(color))

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

        # creates user if doesn't exist
        await self._create_user(user, server)

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        serverbadges = await db.badges.find_one({"server_id": str(serverid)})
        if name in serverbadges["badges"].keys():
            del serverbadges["badges"][name]
            await db.badges.update_one(
                {"server_id": serverbadges["server_id"]},
                {"$set": {"badges": serverbadges["badges"]}},
            )
            # remove the badge if there
            async for user_info_temp in db.users.find({}):
                try:
                    user_info_temp = await self._badge_convert_dict(user_info_temp)

                    badge_name = "{}_{}".format(name, serverid)
                    if badge_name in user_info_temp["badges"].keys():
                        del user_info_temp["badges"][badge_name]
                        await db.users.update_one(
                            {"user_id": user_info_temp["user_id"]},
                            {"$set": {"badges": user_info_temp["badges"]}},
                        )
                except Exception as exc:
                    log.error(
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
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        serverbadges = await db.badges.find_one({"server_id": str(server.id)})
        badges = serverbadges["badges"]
        badge_name = "{}_{}".format(name, server.id)

        if name not in badges:
            await ctx.send("**That badge doesn't exist in this server!**")
            return
        if badge_name in badges.keys():
            await ctx.send(
                "**{} already has that badge!**".format(await self._is_mention(user))
            )
            return
        userinfo["badges"][badge_name] = badges[name]
        await db.users.update_one(
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
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        serverbadges = await db.badges.find_one({"server_id": str(server.id)})
        badges = serverbadges["badges"]
        badge_name = "{}_{}".format(name, server.id)

        if name not in badges:
            await ctx.send("**That badge doesn't exist in this server!**")
        elif badge_name not in userinfo["badges"]:
            await ctx.send(
                "**{} does not have that badge!**".format(await self._is_mention(user))
            )
        else:
            if userinfo["badges"][badge_name]["price"] == -1:
                del userinfo["badges"][badge_name]
                await db.users.update_one(
                    {"user_id": str(user.id)}, {"$set": {"badges": userinfo["badges"]}}
                )
                await ctx.send(
                    "**{} has taken the `{}` badge from {}! :upside_down:**".format(
                        await self._is_mention(org_user),
                        name,
                        await self._is_mention(user),
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
        serverbadges = await db.badges.find_one({"server_id": str(server.id)})

        if serverbadges is None:
            await ctx.send("**This server does not have any badges!**")
            return

        if badge_name not in serverbadges["badges"].keys():
            await ctx.send(
                "**Please make sure the `{}` badge exists!**".format(badge_name)
            )
            return
        server_linked_badges = await db.badgelinks.find_one(
            {"server_id": str(server.id)}
        )
        if not server_linked_badges:
            new_server = {
                "server_id": str(server.id),
                "badges": {badge_name: str(level)},
            }
            await db.badgelinks.insert_one(new_server)
        else:
            server_linked_badges["badges"][badge_name] = str(level)
            await db.badgelinks.update_one(
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

        server_linked_badges = await db.badgelinks.find_one(
            {"server_id": str(server.id)}
        )
        badge_links = server_linked_badges["badges"]

        if badge_name in badge_links.keys():
            await ctx.send(
                "**Badge/Level association `{}`/`{}` removed.**".format(
                    badge_name, badge_links[badge_name]
                )
            )
            del badge_links[badge_name]
            await db.badgelinks.update_one(
                {"server_id": str(server.id)}, {"$set": {"badges": badge_links}}
            )
        else:
            await ctx.send(
                "**The `{}` badge is not linked to any levels!**".format(badge_name)
            )

    @checks.mod_or_permissions(manage_roles=True)
    @badge.command(name="listlinks")
    @commands.guild_only()
    async def listbadge(self, ctx):
        """List level/badge associations."""
        server = ctx.guild

        server_badges = await db.badgelinks.find_one({"server_id": str(server.id)})

        em = discord.Embed(colour=await ctx.embed_color())
        em.set_author(
            name="Current Badge - Level Links for {}".format(server.name),
            icon_url=server.icon_url,
        )

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

        em.description = msg
        await ctx.send(embed=em)

    @lvladmin.group()
    async def role(self, ctx):
        """Admin role configuration."""
        pass

    @checks.mod_or_permissions(manage_roles=True)
    @role.command(name="link")
    @commands.guild_only()
    async def linkrole(self, ctx, add_role: discord.Role, level: int, remove_role: discord.Role = None):
        """Associate a role with a level.

        Removes previous role if given."""
        server = ctx.guild

        server_roles = await db.roles.find_one({"server_id": str(server.id)})
        if not server_roles:
            new_server = {
                "server_id": str(server.id),
                "roles": {
                    add_role.name: {"level": str(level), "remove_role": remove_role.name if remove_role else None}
                },
            }
            await db.roles.insert_one(new_server)
        else:
            if add_role.name not in server_roles["roles"]:
                server_roles["roles"][add_role.name] = {}

            server_roles["roles"][add_role.name]["level"] = str(level)
            server_roles["roles"][add_role.name]["remove_role"] = remove_role.name if remove_role else None
            await db.roles.update_one(
                {"server_id": str(server.id)},
                {"$set": {"roles": server_roles["roles"]}},
            )

        if remove_role:
            await ctx.send(
                "**The `{}` role has been linked to level `{}`. "
                "Will also remove `{}` role.**".format(
                    add_role, level, remove_role
                )
            )
        else:
            await ctx.send(
                "**The `{}` role has been linked to level `{}`**".format(
                    add_role, level
                )
            )

    @checks.mod_or_permissions(manage_roles=True)
    @role.command(name="unlink", usage="<role>")
    @commands.guild_only()
    async def unlinkrole(self, ctx, *, role_to_unlink: discord.Role):
        """Delete a role/level association."""
        server = ctx.guild

        server_roles = await db.roles.find_one({"server_id": str(server.id)})
        roles = server_roles["roles"]

        if role_to_unlink.name in roles:
            await ctx.send(
                "**Role/Level association `{}`/`{}` removed.**".format(
                    role_to_unlink.name, roles[role_to_unlink.name]["level"]
                )
            )
            del roles[role_to_unlink.name]
            await db.roles.update_one(
                {"server_id": str(server.id)}, {"$set": {"roles": roles}}
            )
        else:
            await ctx.send(
                "**The `{}` role is not linked to any levels!**".format(role_to_unlink.name)
            )

    @checks.mod_or_permissions(manage_roles=True)
    @role.command(name="listlinks")
    @commands.guild_only()
    async def listrole(self, ctx):
        """List level/role associations."""
        server = ctx.guild

        server_roles = await db.roles.find_one({"server_id": str(server.id)})

        em = discord.Embed(colour=await ctx.embed_color())
        em.set_author(
            name="Current Role - Level Links for {}".format(server.name),
            icon_url=server.icon_url,
        )

        if server_roles is None or not server_roles.get("roles"):
            msg = "None"
        else:
            sortorder = sorted(
                server_roles["roles"],
                key=lambda r: int(server_roles["roles"][r]["level"]),
            )
            roles = OrderedDict(server_roles["roles"])
            for k in sortorder:
                roles.move_to_end(k)
            msg = "**Role** → Level\n"
            for role in roles:
                if roles[role]["remove_role"]:
                    msg += "**• {} →** {} (Removes: {})\n".format(
                        role, roles[role]["level"], roles[role]["remove_role"]
                    )
                else:
                    msg += "**• {} →** {}\n".format(role, roles[role]["level"])

        em.description = msg
        await ctx.send(embed=em)

    @lvladmin.group(name="bg")
    async def lvladminbg(self, ctx):
        """Admin background configuration"""
        pass

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def addprofilebg(self, ctx, name: str, url: str):
        """Add a profile background. 
        
        The proportions must be 290px x 290px."""
        backgrounds = await self.config.backgrounds()
        if name in backgrounds["profile"].keys():
            await ctx.send("**That profile background name already exists!**")
        elif not await self._valid_image_url(url):
            await ctx.send("**That is not a valid image URL!**")
        else:
            async with self.config.backgrounds() as backgrounds:
                backgrounds["profile"][name] = url
            await ctx.send("**New profile background (`{}`) added.**".format(name))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def addrankbg(self, ctx, name: str, url: str):
        """Add a rank background.

        The proportions must be 360px x 100px."""
        backgrounds = await self.config.backgrounds()
        if name in backgrounds["profile"].keys():
            await ctx.send("**That rank background name already exists!**")
        elif not await self._valid_image_url(url):
            await ctx.send("**That is not a valid image URL!**")
        else:
            async with self.config.backgrounds() as backgrounds:
                backgrounds["rank"][name] = url
            await ctx.send("**New rank background (`{}`) added.**".format(name))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def addlevelbg(self, ctx, name: str, url: str):
        """Add a level-up background.

        The proportions must be 175px x 65px."""
        backgrounds = await self.config.backgrounds()
        if name in backgrounds["levelup"].keys():
            await ctx.send("**That level-up background name already exists!**")
        elif not await self._valid_image_url(url):
            await ctx.send("**That is not a valid image URL!**")
        else:
            async with self.config.backgrounds() as backgrounds:
                backgrounds["levelup"][name] = url
            await ctx.send("**New level-up background (`{}`) added.**".format(name))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def setcustombg(self, ctx, bg_type: str, user_id: str, img_url: str):
        """Set one-time custom background

        bg_type can be: `profile`, `rank` or `levelup`."""
        valid_types = ["profile", "rank", "levelup"]
        type_input = bg_type.lower()

        if type_input not in valid_types:
            await ctx.send(
                "**Please choose a valid type. Must be `profile`, `rank` or `levelup`."
            )
            return

        # test if valid user_id
        userinfo = await db.users.find_one({"user_id": str(user_id)})
        if not userinfo:
            await ctx.send("**That is not a valid user id!**")
            return

        if not await self._valid_image_url(img_url):
            await ctx.send("**That is not a valid image URL!**")
            return

        await db.users.update_one(
            {"user_id": str(user_id)},
            {"$set": {"{}_background".format(type_input): img_url}},
        )
        await ctx.send("**User {} custom {} background set.**".format(user_id, bg_type))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def delprofilebg(self, ctx, name: str):
        """Delete a profile background."""
        bgs = await self.config.backgrounds()
        if name in bgs["profile"].keys():
            await self.config.clear_raw("backgrounds", "profile", name)
            await ctx.send(
                "**The profile background(`{}`) has been deleted.**".format(name)
            )
        else:
            await ctx.send("**That profile background name doesn't exist.**")

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def delrankbg(self, ctx, name: str):
        """Delete a rank background."""
        bgs = await self.config.backgrounds()
        if name in bgs["rank"].keys():
            await self.config.clear_raw("backgrounds", "rank", name)
            await ctx.send(
                "**The rank background(`{}`) has been deleted.**".format(name)
            )
        else:
            await ctx.send("**That rank background name doesn't exist.**")

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def dellevelbg(self, ctx, name: str):
        """Delete a level background."""
        bgs = await self.config.backgrounds()
        if name in bgs["levelup"].keys():
            await self.config.clear_raw("backgrounds", "levelup", name)
            await ctx.send(
                "**The level-up background(`{}`) has been deleted.**".format(name)
            )
        else:
            await ctx.send("**That level-up background name doesn't exist.**")

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

    async def draw_profile(self, user, server):
        font_thin_file = f"{bundled_data_path(self)}/Uni_Sans_Thin.ttf"
        font_heavy_file = f"{bundled_data_path(self)}/Uni_Sans_Heavy.ttf"
        font_file = f"{bundled_data_path(self)}/Ubuntu-R_0.ttf"
        font_bold_file = f"{bundled_data_path(self)}/Ubuntu-B_0.ttf"

        name_fnt = ImageFont.truetype(font_heavy_file, 30)
        name_u_fnt = ImageFont.truetype(self.font_unicode_file, 30)
        title_fnt = ImageFont.truetype(font_heavy_file, 22)
        title_u_fnt = ImageFont.truetype(self.font_unicode_file, 23)
        label_fnt = ImageFont.truetype(font_bold_file, 18)
        exp_fnt = ImageFont.truetype(font_bold_file, 13)
        large_fnt = ImageFont.truetype(font_thin_file, 33)
        rep_fnt = ImageFont.truetype(font_heavy_file, 26)
        rep_u_fnt = ImageFont.truetype(self.font_unicode_file, 30)
        text_fnt = ImageFont.truetype(font_file, 14)
        text_u_fnt = ImageFont.truetype(self.font_unicode_file, 14)
        symbol_u_fnt = ImageFont.truetype(self.font_unicode_file, 15)

        async def _write_unicode(text, init_x, y, font, unicode_font, fill):
            write_pos = init_x
            check_font = TTFont(font.path)

            for char in text:
                # if char.isalnum() or char in string.punctuation or char in string.whitespace:
                if await self.char_in_font(char, check_font):
                    draw.text((write_pos, y), "{}".format(char), font=font, fill=fill)
                    write_pos += font.getsize(char)[0]
                else:
                    draw.text(
                        (write_pos, y), "{}".format(char), font=unicode_font, fill=fill
                    )
                    write_pos += unicode_font.getsize(char)[0]

        # get urls
        userinfo = await db.users.find_one({"user_id": str(user.id)})
        await self._badge_convert_dict(userinfo)
        userinfo = await db.users.find_one({"user_id": str(user.id)})
        bg_url = userinfo["profile_background"]

        # COLORS
        white_color = (240, 240, 240, 255)
        if "rep_color" not in userinfo.keys() or not userinfo["rep_color"]:
            rep_fill = (92, 130, 203, 230)
        else:
            rep_fill = tuple(userinfo["rep_color"])
        # determines badge section color, should be behind the titlebar
        if "badge_col_color" not in userinfo.keys() or not userinfo["badge_col_color"]:
            badge_fill = (128, 151, 165, 230)
        else:
            badge_fill = tuple(userinfo["badge_col_color"])
        if "profile_info_color" in userinfo.keys():
            info_fill = tuple(userinfo["profile_info_color"])
        else:
            info_fill = (30, 30, 30, 220)
        info_fill_tx = (info_fill[0], info_fill[1], info_fill[2], 150)
        if (
            "profile_exp_color" not in userinfo.keys()
            or not userinfo["profile_exp_color"]
        ):
            exp_fill = (255, 255, 255, 230)
        else:
            exp_fill = tuple(userinfo["profile_exp_color"])
        if badge_fill == (128, 151, 165, 230):
            level_fill = white_color
        else:
            level_fill = self._contrast(exp_fill, rep_fill, badge_fill)

        async with self.session.get(bg_url) as r:
            image = await r.content.read()
            profile_background = BytesIO(image)
        profile_avatar = BytesIO()
        await user.avatar_url_as(format=AVATAR_FORMAT).save(
            profile_avatar, seek_begin=True
        )

        bg_image = Image.open(profile_background).convert("RGBA")
        profile_image = Image.open(profile_avatar).convert("RGBA")

        # set canvas
        bg_color = (255, 255, 255, 0)
        result = Image.new("RGBA", (340, 390), bg_color)
        process = Image.new("RGBA", (340, 390), bg_color)

        # draw
        draw = ImageDraw.Draw(process)

        # puts in background
        bg_image = bg_image.resize((340, 340), Image.ANTIALIAS)
        bg_image = bg_image.crop((0, 0, 340, 305))
        result.paste(bg_image, (0, 0))

        # draw filter
        draw.rectangle([(0, 0), (340, 340)], fill=(0, 0, 0, 10))

        draw.rectangle([(0, 134), (340, 325)], fill=info_fill_tx)  # general content
        # draw profile circle
        multiplier = 8
        lvl_circle_dia = 116
        circle_left = 14
        circle_top = 48
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # border
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse(
            [0, 0, raw_length, raw_length],
            fill=(255, 255, 255, 255),
            outline=(255, 255, 255, 250),
        )
        # put border
        lvl_circle = lvl_circle.resize(
            (lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS
        )
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        # put in profile picture
        total_gap = 6
        border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize(
            (profile_size, profile_size), Image.ANTIALIAS
        )
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # write label text
        white_color = (240, 240, 240, 255)
        light_color = (160, 160, 160, 255)
        dark_color = (35, 35, 35, 255)

        head_align = 140
        # determine info text color
        info_text_color = self._contrast(info_fill, white_color, dark_color)
        await _write_unicode(
            (await self._truncate_text(user.name, 22)).upper(),
            head_align,
            142,
            name_fnt,
            name_u_fnt,
            info_text_color,
        )  # NAME
        await _write_unicode(
            userinfo["title"].upper(),
            head_align,
            170,
            title_fnt,
            title_u_fnt,
            info_text_color,
        )

        # draw divider
        draw.rectangle([(0, 323), (340, 324)], fill=(0, 0, 0, 255))  # box
        # draw text box
        draw.rectangle(
            [(0, 324), (340, 390)], fill=(info_fill[0], info_fill[1], info_fill[2], 255)
        )  # box

        # rep_text = "{} REP".format(userinfo["rep"])
        rep_text = "{}".format(userinfo["rep"])
        await _write_unicode("❤", 257, 9, rep_fnt, rep_u_fnt, rep_fill)
        draw.text(
            (await self._center(278, 340, rep_text, rep_fnt), 10),
            rep_text,
            font=rep_fnt,
            fill=rep_fill,
        )  # Exp Text

        label_align = 362  # vertical
        draw.text(
            (await self._center(0, 140, "    RANK", label_fnt), label_align),
            "    RANK",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (await self._center(0, 340, "    LEVEL", label_fnt), label_align),
            "    LEVEL",
            font=label_fnt,
            fill=info_text_color,
        )  # Exp
        draw.text(
            (await self._center(200, 340, "BALANCE", label_fnt), label_align),
            "BALANCE",
            font=label_fnt,
            fill=info_text_color,
        )  # Credits

        if "linux" in platform.system().lower():
            global_symbol = "\U0001F30E "
        else:
            global_symbol = "G."

        await _write_unicode(
            global_symbol, 36, label_align + 5, label_fnt, symbol_u_fnt, info_text_color
        )  # Symbol
        await _write_unicode(
            global_symbol,
            134,
            label_align + 5,
            label_fnt,
            symbol_u_fnt,
            info_text_color,
        )  # Symbol

        # userinfo
        global_rank = "#{}".format(await self._find_global_rank(user))
        global_level = "{}".format(await self._find_level(userinfo["total_exp"]))
        draw.text(
            (await self._center(0, 140, global_rank, large_fnt), label_align - 27),
            global_rank,
            font=large_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (await self._center(0, 340, global_level, large_fnt), label_align - 27),
            global_level,
            font=large_fnt,
            fill=info_text_color,
        )  # Exp
        # draw level bar
        exp_font_color = self._contrast(exp_fill, light_color, dark_color)
        exp_frac = int(userinfo["total_exp"] - await self._level_exp(int(global_level)))
        exp_total = await self._required_exp(int(global_level) + 1)
        bar_length = int(exp_frac / exp_total * 340)
        draw.rectangle(
            [(0, 305), (340, 323)],
            fill=(level_fill[0], level_fill[1], level_fill[2], 245),
        )  # level box
        draw.rectangle(
            [(0, 305), (bar_length, 323)],
            fill=(exp_fill[0], exp_fill[1], exp_fill[2], 255),
        )  # box
        exp_text = "{}/{}".format(exp_frac, exp_total)  # Exp
        draw.text(
            (await self._center(0, 340, exp_text, exp_fnt), 305),
            exp_text,
            font=exp_fnt,
            fill=exp_font_color,
        )  # Exp Text

        bank_credits = await bank.get_balance(user)
        credit_txt = f"{bank_credits}{(await bank.get_currency_name(server))[0]}"
        draw.text(
            (await self._center(200, 340, credit_txt, large_fnt), label_align - 27),
            credit_txt,
            font=large_fnt,
            fill=info_text_color,
        )  # Credits

        if not userinfo["title"]:
            offset = 170
        else:
            offset = 195
        margin = 140
        txt_color = self._contrast(info_fill, white_color, dark_color)
        for line in textwrap.wrap(userinfo["info"], width=32):
            # for line in textwrap.wrap('userinfo["info"]', width=200):
            # draw.text((margin, offset), line, font=text_fnt, fill=white_color)
            await _write_unicode(line, margin, offset, text_fnt, text_u_fnt, txt_color)
            offset += text_fnt.getsize(line)[1] + 2

        # sort badges
        priority_badges = []

        for badgename in userinfo["badges"].keys():
            badge = userinfo["badges"][badgename]
            priority_num = badge["priority_num"]
            if priority_num != 0 and priority_num != -1:
                priority_badges.append((badge, priority_num))
        sorted_badges = sorted(
            priority_badges, key=operator.itemgetter(1), reverse=True
        )

        if await self.config.badge_type() == "circles":
            # circles require antialiasing
            vert_pos = 172
            right_shift = 0
            left = 9 + right_shift
            size = 38
            total_gap = 4  # /2
            hor_gap = 6
            vert_gap = 6
            border_width = int(total_gap / 2)
            multiplier = 6  # for antialiasing
            raw_length = size * multiplier
            mult = [
                (0, 0),
                (1, 0),
                (2, 0),
                (0, 1),
                (1, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            ]
            for num in range(9):
                coord = (
                    left + int(mult[num][0]) * int(hor_gap + size),
                    vert_pos + int(mult[num][1]) * int(vert_gap + size),
                )
                if num < len(sorted_badges[:9]):
                    pair = sorted_badges[num]
                    badge = pair[0]
                    bg_color = badge["bg_img"]
                    border_color = badge["border_color"]
                    # draw mask circle
                    mask = Image.new("L", (raw_length, raw_length), 0)
                    draw_thumb = ImageDraw.Draw(mask)
                    draw_thumb.ellipse(
                        (0, 0) + (raw_length, raw_length), fill=255, outline=0
                    )

                    # determine image or color for badge bg
                    if await self._valid_image_url(bg_color):
                        # get image
                        async with self.session.get(bg_color) as r:
                            image = await r.content.read()
                        badge = BytesIO(image)
                        badge_image = Image.open(badge).convert("RGBA")
                        badge_image = badge_image.resize(
                            (raw_length, raw_length), Image.ANTIALIAS
                        )

                        # structured like this because if border = 0, still leaves outline.
                        if border_color:
                            square = Image.new(
                                "RGBA", (raw_length, raw_length), border_color
                            )
                            # put border on ellipse/circle
                            output = ImageOps.fit(
                                square, (raw_length, raw_length), centering=(0.5, 0.5)
                            )
                            output = output.resize((size, size), Image.ANTIALIAS)
                            outer_mask = mask.resize((size, size), Image.ANTIALIAS)
                            process.paste(output, coord, outer_mask)

                            # put on ellipse/circle
                            output = ImageOps.fit(
                                badge_image,
                                (raw_length, raw_length),
                                centering=(0.5, 0.5),
                            )
                            output = output.resize(
                                (size - total_gap, size - total_gap), Image.ANTIALIAS
                            )
                            inner_mask = mask.resize(
                                (size - total_gap, size - total_gap), Image.ANTIALIAS
                            )
                            process.paste(
                                output,
                                (coord[0] + border_width, coord[1] + border_width),
                                inner_mask,
                            )
                        else:
                            # put on ellipse/circle
                            output = ImageOps.fit(
                                badge_image,
                                (raw_length, raw_length),
                                centering=(0.5, 0.5),
                            )
                            output = output.resize((size, size), Image.ANTIALIAS)
                            outer_mask = mask.resize((size, size), Image.ANTIALIAS)
                            process.paste(output, coord, outer_mask)
                else:
                    plus_fill = exp_fill
                    # put on ellipse/circle
                    plus_square = Image.new("RGBA", (raw_length, raw_length))
                    plus_draw = ImageDraw.Draw(plus_square)
                    plus_draw.rectangle(
                        [(0, 0), (raw_length, raw_length)],
                        fill=(info_fill[0], info_fill[1], info_fill[2], 245),
                    )
                    # draw plus signs
                    margin = 60
                    thickness = 40
                    v_left = int(raw_length / 2 - thickness / 2)
                    v_right = v_left + thickness
                    v_top = margin
                    v_bottom = raw_length - margin
                    plus_draw.rectangle(
                        [(v_left, v_top), (v_right, v_bottom)],
                        fill=(plus_fill[0], plus_fill[1], plus_fill[2], 245),
                    )
                    h_left = margin
                    h_right = raw_length - margin
                    h_top = int(raw_length / 2 - thickness / 2)
                    h_bottom = h_top + thickness
                    plus_draw.rectangle(
                        [(h_left, h_top), (h_right, h_bottom)],
                        fill=(plus_fill[0], plus_fill[1], plus_fill[2], 245),
                    )
                    # put border on ellipse/circle
                    output = ImageOps.fit(
                        plus_square, (raw_length, raw_length), centering=(0.5, 0.5)
                    )
                    output = output.resize((size, size), Image.ANTIALIAS)
                    outer_mask = mask.resize((size, size), Image.ANTIALIAS)
                    process.paste(output, coord, outer_mask)

        result = Image.alpha_composite(result, process)
        result = await self._add_corners(result, 25)
        file = BytesIO()
        result.save(file, "PNG", quality=100)
        file.seek(0)
        return file

    # returns color that contrasts better in background
    def _contrast(self, bg_color, color1, color2):
        color1_ratio = self._contrast_ratio(bg_color, color1)
        color2_ratio = self._contrast_ratio(bg_color, color2)
        if color1_ratio >= color2_ratio:
            return color1
        return color2

    def _luminance(self, color):
        # convert to greyscale
        luminance = float(
            (0.2126 * color[0]) + (0.7152 * color[1]) + (0.0722 * color[2])
        )
        return luminance

    def _contrast_ratio(self, bgcolor, foreground):
        f_lum = float(self._luminance(foreground) + 0.05)
        bg_lum = float(self._luminance(bgcolor) + 0.05)

        if bg_lum > f_lum:
            return bg_lum / f_lum
        return f_lum / bg_lum

    # returns a string with possibly a nickname
    async def _name(self, user, max_length):
        if user.name == user.display_name:
            return user.name
        return "{} ({})".format(
            user.name,
            await self._truncate_text(
                user.display_name, max_length - len(user.name) - 3
            ),
            max_length,
        )

    async def _add_dropshadow(
        self,
        image,
        offset=(4, 4),
        background=0x000,
        shadow=0x0F0,
        border=3,
        iterations=5,
    ):
        total_width = image.size[0] + abs(offset[0]) + 2 * border
        total_height = image.size[1] + abs(offset[1]) + 2 * border
        back = Image.new(image.mode, (total_width, total_height), background)

        # Place the shadow, taking into account the offset from the image
        shadow_left = border + max(offset[0], 0)
        shadow_top = border + max(offset[1], 0)
        back.paste(
            shadow,
            [
                shadow_left,
                shadow_top,
                shadow_left + image.size[0],
                shadow_top + image.size[1],
            ],
        )

        n = 0
        while n < iterations:
            back = back.filter(ImageFilter.BLUR)
            n += 1

        # Paste the input image onto the shadow backdrop
        image_left = border - min(offset[0], 0)
        image_top = border - min(offset[1], 0)
        back.paste(image, (image_left, image_top))
        return back

    async def draw_rank(self, user, server):
        # fonts
        font_thin_file = f"{bundled_data_path(self)}/Uni_Sans_Thin.ttf"
        font_heavy_file = f"{bundled_data_path(self)}/Uni_Sans_Heavy.ttf"
        font_bold_file = f"{bundled_data_path(self)}/SourceSansPro-Semibold.ttf"

        name_fnt = ImageFont.truetype(font_heavy_file, 24)
        name_u_fnt = ImageFont.truetype(self.font_unicode_file, 24)
        label_fnt = ImageFont.truetype(font_bold_file, 16)
        exp_fnt = ImageFont.truetype(font_bold_file, 9)
        large_fnt = ImageFont.truetype(font_thin_file, 24)
        symbol_u_fnt = ImageFont.truetype(self.font_unicode_file, 15)

        async def _write_unicode(text, init_x, y, font, unicode_font, fill):
            write_pos = init_x
            check_font = TTFont(font.path)

            for char in text:
                # if char.isalnum() or char in string.punctuation or char in string.whitespace:
                if await self.char_in_font(char, check_font):
                    draw.text((write_pos, y), "{}".format(char), font=font, fill=fill)
                    write_pos += font.getsize(char)[0]
                else:
                    draw.text(
                        (write_pos, y), "{}".format(char), font=unicode_font, fill=fill
                    )
                    write_pos += unicode_font.getsize(char)[0]

        userinfo = await db.users.find_one({"user_id": str(user.id)})
        # get urls
        bg_url = userinfo["rank_background"]

        async with self.session.get(bg_url) as r:
            image = await r.content.read()
        rank_background = BytesIO(image)
        rank_avatar = BytesIO()
        await user.avatar_url_as(format=AVATAR_FORMAT).save(
            rank_avatar, seek_begin=True
        )

        bg_image = Image.open(rank_background).convert("RGBA")
        profile_image = Image.open(rank_avatar).convert("RGBA")

        # set canvas
        width = 390
        height = 100
        bg_color = (255, 255, 255, 0)
        bg_width = width - 50
        result = Image.new("RGBA", (width, height), bg_color)
        process = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(process)

        # info section
        info_section = Image.new("RGBA", (bg_width, height), bg_color)
        info_section_process = Image.new("RGBA", (bg_width, height), bg_color)
        # puts in background
        bg_image = bg_image.resize((width, height), Image.ANTIALIAS)
        bg_image = bg_image.crop((0, 0, width, height))
        info_section.paste(bg_image, (0, 0))

        # draw transparent overlays
        draw_overlay = ImageDraw.Draw(info_section_process)
        draw_overlay.rectangle([(0, 0), (bg_width, 20)], fill=(230, 230, 230, 200))
        draw_overlay.rectangle(
            [(0, 20), (bg_width, 30)], fill=(120, 120, 120, 180)
        )  # Level bar
        exp_frac = int(userinfo["servers"][str(server.id)]["current_exp"])
        exp_total = await self._required_exp(
            userinfo["servers"][str(server.id)]["level"]
        )
        exp_width = int(bg_width * (exp_frac / exp_total))
        if "rank_info_color" in userinfo.keys():
            exp_color = tuple(userinfo["rank_info_color"])
            exp_color = (
                exp_color[0],
                exp_color[1],
                exp_color[2],
                180,
            )  # increase transparency
        else:
            exp_color = (140, 140, 140, 230)
        draw_overlay.rectangle([(0, 20), (exp_width, 30)], fill=exp_color)  # Exp bar
        draw_overlay.rectangle(
            [(0, 30), (bg_width, 31)], fill=(0, 0, 0, 255)
        )  # Divider
        # draw_overlay.rectangle([(0,35), (bg_width,100)], fill=(230,230,230,0)) # title overlay
        for i in range(0, 70):
            draw_overlay.rectangle(
                [(0, height - i), (bg_width, height - i)],
                fill=(20, 20, 20, 255 - i * 3),
            )  # title overlay

        # draw corners and finalize
        info_section = Image.alpha_composite(info_section, info_section_process)
        info_section = await self._add_corners(info_section, 25)
        process.paste(info_section, (35, 0))

        # draw level circle
        multiplier = 6
        lvl_circle_dia = 100
        circle_left = 0
        circle_top = int((height - lvl_circle_dia) / 2)
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # drawing level border
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse(
            [0, 0, raw_length, raw_length], fill=(250, 250, 250, 250)
        )
        # put on profile circle background
        lvl_circle = lvl_circle.resize(
            (lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS
        )
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        # draws mask
        total_gap = 6
        border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(
            profile_image, (raw_length, raw_length), centering=(0.5, 0.5)
        )
        output.resize((profile_size, profile_size), Image.ANTIALIAS)
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize(
            (profile_size, profile_size), Image.ANTIALIAS
        )
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # draw text
        grey_color = (100, 100, 100, 255)
        white_color = (220, 220, 220, 255)

        # name
        await _write_unicode(
            await self._truncate_text(await self._name(user, 20), 20),
            100,
            0,
            name_fnt,
            name_u_fnt,
            grey_color,
        )  # Name

        # labels
        v_label_align = 75
        info_text_color = white_color
        draw.text(
            (await self._center(100, 200, "  RANK", label_fnt), v_label_align),
            "  RANK",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (await self._center(100, 360, "  LEVEL", label_fnt), v_label_align),
            "  LEVEL",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (await self._center(260, 360, "BALANCE", label_fnt), v_label_align),
            "BALANCE",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        if "linux" in platform.system().lower():
            local_symbol = "\U0001F3E0 "
        else:
            local_symbol = "S. "
        await _write_unicode(
            local_symbol,
            117,
            v_label_align + 4,
            label_fnt,
            symbol_u_fnt,
            info_text_color,
        )  # Symbol
        await _write_unicode(
            local_symbol,
            195,
            v_label_align + 4,
            label_fnt,
            symbol_u_fnt,
            info_text_color,
        )  # Symbol

        # userinfo
        server_rank = "#{}".format(await self._find_server_rank(user, server))
        draw.text(
            (await self._center(100, 200, server_rank, large_fnt), v_label_align - 30),
            server_rank,
            font=large_fnt,
            fill=info_text_color,
        )  # Rank
        level_text = "{}".format(userinfo["servers"][str(server.id)]["level"])
        draw.text(
            (await self._center(95, 360, level_text, large_fnt), v_label_align - 30),
            level_text,
            font=large_fnt,
            fill=info_text_color,
        )  # Level
        bank_credits = await bank.get_balance(user)
        credit_txt = f"{bank_credits}{(await bank.get_currency_name(server))[0]}"
        draw.text(
            (await self._center(260, 360, credit_txt, large_fnt), v_label_align - 30),
            credit_txt,
            font=large_fnt,
            fill=info_text_color,
        )  # Balance
        exp_text = "{}/{}".format(exp_frac, exp_total)
        draw.text(
            (await self._center(80, 360, exp_text, exp_fnt), 19),
            exp_text,
            font=exp_fnt,
            fill=info_text_color,
        )  # Rank

        result = Image.alpha_composite(result, process)
        file = BytesIO()
        result.save(file, "PNG", quality=100)
        file.seek(0)
        return file

    async def _add_corners(self, im, rad, multiplier=6):
        raw_length = rad * 2 * multiplier
        circle = Image.new("L", (raw_length, raw_length), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, raw_length, raw_length), fill=255)
        circle = circle.resize((rad * 2, rad * 2), Image.ANTIALIAS)

        alpha = Image.new("L", im.size, 255)
        w, h = im.size
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        im.putalpha(alpha)
        return im

    async def draw_levelup(self, user, server):
        # fonts
        font_thin_file = f"{bundled_data_path(self)}/Uni_Sans_Thin.ttf"
        level_fnt = ImageFont.truetype(font_thin_file, 23)

        userinfo = await db.users.find_one({"user_id": str(user.id)})

        # get urls
        bg_url = userinfo["levelup_background"]

        async with self.session.get(bg_url) as r:
            image = await r.content.read()
        level_background = BytesIO(image)
        level_avatar = BytesIO()
        await user.avatar_url_as(format=AVATAR_FORMAT).save(
            level_avatar, seek_begin=True
        )

        bg_image = Image.open(level_background).convert("RGBA")
        profile_image = Image.open(level_avatar).convert("RGBA")

        # set canvas
        width = 176
        height = 67
        bg_color = (255, 255, 255, 0)
        result = Image.new("RGBA", (width, height), bg_color)
        process = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(process)

        # puts in background
        bg_image = bg_image.resize((width, height), Image.ANTIALIAS)
        bg_image = bg_image.crop((0, 0, width, height))
        result.paste(bg_image, (0, 0))

        # info section
        lvl_circle_dia = 60
        total_gap = 2
        border = int(total_gap / 2)
        info_section = Image.new("RGBA", (165, 55), (230, 230, 230, 20))
        info_section = await self._add_corners(info_section, int(lvl_circle_dia / 2))
        process.paste(info_section, (border, border))

        # draw transparent overlay
        if "levelup_info_color" in userinfo.keys():
            info_color = tuple(userinfo["levelup_info_color"])
            info_color = (
                info_color[0],
                info_color[1],
                info_color[2],
                150,
            )  # increase transparency
        else:
            info_color = (30, 30, 30, 150)

        for i in range(0, height):
            draw.rectangle(
                [(0, height - i), (width, height - i)],
                fill=(info_color[0], info_color[1], info_color[2], 255 - i * 3),
            )  # title overlay

        # draw circle
        multiplier = 6
        circle_left = 4
        circle_top = int((height - lvl_circle_dia) / 2)
        raw_length = lvl_circle_dia * multiplier
        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # border
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse(
            [0, 0, raw_length, raw_length], fill=(250, 250, 250, 180)
        )
        lvl_circle = lvl_circle.resize(
            (lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS
        )
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(
            profile_image, (raw_length, raw_length), centering=(0.5, 0.5)
        )
        output.resize((profile_size, profile_size), Image.ANTIALIAS)
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize(
            (profile_size, profile_size), Image.ANTIALIAS
        )
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # write label text
        white_text = (250, 250, 250, 255)
        dark_text = (35, 35, 35, 230)
        level_up_text = self._contrast(info_color, white_text, dark_text)
        lvl_text = "LEVEL {}".format(userinfo["servers"][str(server.id)]["level"])
        draw.text(
            (await self._center(60, 170, lvl_text, level_fnt), 23),
            lvl_text,
            font=level_fnt,
            fill=level_up_text,
        )  # Level Number

        result = Image.alpha_composite(result, process)
        result = await self._add_corners(result, int(height / 2))
        file = BytesIO()
        result.save(file, "PNG", quality=100)
        file.seek(0)
        return file

    @commands.Cog.listener("on_message_without_command")
    async def _handle_on_message(self, message):
        server = message.guild
        user = message.author
        xp = await self.config.xp()
        # creates user if doesn't exist, bots are not logged.
        await self._create_user(user, server)
        curr_time = time.time()
        userinfo = await db.users.find_one({"user_id": str(user.id)})

        if not server or await self.config.guild(server).disabled():
            return
        if user.bot:
            return

        # check if chat_block exists
        if "chat_block" not in userinfo:
            userinfo["chat_block"] = 0

        if "last_message" not in userinfo:
            userinfo["last_message"] = 0
        if all(
            [
                float(curr_time) - float(userinfo["chat_block"]) >= 120,
                len(message.content) > await self.config.message_length()
                or message.attachments,
                message.content != userinfo["last_message"],
                message.channel.id
                not in await self.config.guild(server).ignored_channels(),
            ]
        ):
            await self._process_exp(message, userinfo, random.randint(xp[0], xp[1]))
            await self._give_chat_credit(user, server)

    async def _process_exp(self, message, userinfo, exp: int):
        server = message.guild
        channel = message.channel
        user = message.author
        # add to total exp
        required = await self._required_exp(
            userinfo["servers"][str(server.id)]["level"]
        )
        try:
            await db.users.update_one(
                {"user_id": str(user.id)},
                {"$set": {"total_exp": userinfo["total_exp"] + exp}},
            )
            self.bot.dispatch("leveler_process_exp", message, exp)
        except Exception as exc:
            log.error(f"Unable to process xp for {user.id}: {exc}")
        if userinfo["servers"][str(server.id)]["current_exp"] + exp >= required:
            userinfo["servers"][str(server.id)]["level"] += 1
            await db.users.update_one(
                {"user_id": str(user.id)},
                {
                    "$set": {
                        "servers.{}.level".format(server.id): userinfo["servers"][
                            str(server.id)
                        ]["level"],
                        "servers.{}.current_exp".format(server.id): userinfo["servers"][
                            str(server.id)
                        ]["current_exp"]
                        + exp
                        - required,
                        "chat_block": time.time(),
                        "last_message": message.content,
                    }
                },
            )
            await self._handle_levelup(user, userinfo, server, channel)
        else:
            await db.users.update_one(
                {"user_id": str(user.id)},
                {
                    "$set": {
                        "servers.{}.current_exp".format(server.id): userinfo["servers"][
                            str(server.id)
                        ]["current_exp"]
                        + exp,
                        "chat_block": time.time(),
                        "last_message": message.content,
                    }
                },
            )

    async def _handle_levelup(self, user, userinfo, server, channel):
        # channel lock implementation
        channel_id = await self.config.guild(server).lvl_msg_lock()
        if channel_id:
            channel = find(lambda m: m.id == channel_id, server.channels)

        server_identifier = ""  # super hacky
        name = await self._is_mention(user)  # also super hacky
        # private message takes precedent, of course
        if await self.config.guild(server).private_lvl_message():
            server_identifier = f" on {server.name}"
            channel = user
            name = "You"

        new_level = str(userinfo["servers"][str(server.id)]["level"])
        self.bot.dispatch("leveler_levelup", user, new_level)
        # add to appropriate role if necessary
        # try:
        server_roles = await db.roles.find_one({"server_id": str(server.id)})
        if server_roles is not None:
            for role in server_roles["roles"].keys():
                if int(server_roles["roles"][role]["level"]) == int(new_level):
                    add_role = discord.utils.get(server.roles, name=role)
                    if add_role is not None:
                        try:
                            await user.add_roles(add_role, reason="Levelup")
                        except discord.Forbidden:
                            await channel.send(
                                "Levelup role adding failed: Missing Permissions"
                            )
                        except discord.HTTPException:
                            await channel.send("Levelup role adding failed")
                    remove_role = discord.utils.get(
                        server.roles, name=server_roles["roles"][role]["remove_role"]
                    )
                    if remove_role is not None:
                        try:
                            await user.remove_roles(remove_role, reason="Levelup")
                        except discord.Forbidden:
                            await channel.send(
                                "Levelup role removal failed: Missing Permissions"
                            )
                        except discord.HTTPException:
                            await channel.send("Levelup role removal failed")
        try:
            server_linked_badges = await db.badgelinks.find_one(
                {"server_id": str(server.id)}
            )
            if server_linked_badges is not None:
                for badge_name in server_linked_badges["badges"]:
                    if int(server_linked_badges["badges"][badge_name]) == int(
                        new_level
                    ):
                        server_badges = await db.badges.find_one(
                            {"server_id": str(server.id)}
                        )
                        if (
                            server_badges is not None
                            and badge_name in server_badges["badges"].keys()
                        ):
                            userinfo_db = await db.users.find_one(
                                {"user_id": str(user.id)}
                            )
                            new_badge_name = "{}_{}".format(badge_name, server.id)
                            userinfo_db["badges"][new_badge_name] = server_badges[
                                "badges"
                            ][badge_name]
                            await db.users.update_one(
                                {"user_id": str(user.id)},
                                {"$set": {"badges": userinfo_db["badges"]}},
                            )
        except Exception as exc:
            await channel.send(f"Error. Badge was not given: {exc}")

        if await self.config.guild(server).lvl_msg():  # if lvl msg is enabled
            if await self.config.guild(server).text_only():
                async with channel.typing():
                    em = discord.Embed(
                        description="**{} just gained a level{}! (LEVEL {})**".format(
                            name, server_identifier, new_level
                        ),
                        colour=user.colour,
                    )
                    await channel.send(embed=em)
            else:
                async with channel.typing():
                    levelup = await self.draw_levelup(user, server)
                    file = discord.File(levelup, filename="levelup.png")
                    await channel.send(
                        "**{} just gained a level{}!**".format(name, server_identifier),
                        file=file,
                    )

    async def _find_server_rank(self, user, server):
        targetid = str(user.id)
        users = []

        async for userinfo in db.users.find({}):
            try:
                server_exp = 0
                userid = userinfo["user_id"]
                for i in range(userinfo["servers"][str(server.id)]["level"]):
                    server_exp += await self._required_exp(i)
                server_exp += userinfo["servers"][str(server.id)]["current_exp"]
                users.append((userid, server_exp))
            except KeyError:
                pass

        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        async for a_user in self.asyncit(sorted_list):
            if a_user[0] == targetid:
                return rank
            rank += 1

    async def _find_server_rep_rank(self, user, server):
        targetid = str(user.id)
        users = []
        async for userinfo in db.users.find({}):
            if "servers" in userinfo and str(server.id) in userinfo["servers"]:
                users.append((userinfo["user_id"], userinfo["rep"]))

        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        async for a_user in self.asyncit(sorted_list):
            if a_user[0] == targetid:
                return rank
            rank += 1

    async def _find_server_exp(self, user, server):
        server_exp = 0
        userinfo = await db.users.find_one({"user_id": str(user.id)})

        try:
            for i in range(userinfo["servers"][str(server.id)]["level"]):
                server_exp += await self._required_exp(i)
            server_exp += userinfo["servers"][str(server.id)]["current_exp"]
            return server_exp
        except KeyError:
            return server_exp

    async def _find_global_rank(self, user):
        users = []

        async for userinfo in db.users.find({}):
            try:
                userid = userinfo["user_id"]
                users.append((userid, userinfo["total_exp"]))
            except KeyError:
                pass
        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        async for stats in self.asyncit(sorted_list):
            if stats[0] == str(user.id):
                return rank
            rank += 1

    async def _find_global_rep_rank(self, user):
        users = []

        async for userinfo in db.users.find({}):
            try:
                userid = userinfo["user_id"]
                users.append((userid, userinfo["rep"]))
            except KeyError:
                pass
        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        async for stats in self.asyncit(sorted_list):
            if stats[0] == str(user.id):
                return rank
            rank += 1

    # handles user creation, adding new server, blocking
    async def _create_user(self, user, server):
        backgrounds = await self.config.backgrounds()
        if user.bot:
            return
        try:
            userinfo = await db.users.find_one({"user_id": str(user.id)})
            if not userinfo:
                new_account = {
                    "user_id": str(user.id),
                    "username": user.name,
                    "servers": {},
                    "total_exp": 0,
                    "profile_background": backgrounds["profile"]["default"],
                    "rank_background": backgrounds["rank"]["default"],
                    "levelup_background": backgrounds["levelup"]["default"],
                    "title": "",
                    "info": "I am a mysterious person.",
                    "rep": 0,
                    "badges": {},
                    "active_badges": {},
                    "rep_color": [],
                    "badge_col_color": [],
                    "rep_block": 0,
                    "chat_block": 0,
                    "last_message": "",
                    "profile_block": 0,
                    "rank_block": 0,
                }
                await db.users.insert_one(new_account)

            userinfo = await db.users.find_one({"user_id": str(user.id)})

            if "username" not in userinfo or userinfo["username"] != user.name:
                await db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"username": user.name}},
                    upsert=True,
                )

            if "servers" not in userinfo or str(server.id) not in userinfo["servers"]:
                await db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "servers.{}.level".format(server.id): 0,
                            "servers.{}.current_exp".format(server.id): 0,
                        }
                    },
                    upsert=True,
                )
        except AttributeError:
            pass

    async def _truncate_text(self, text, max_length):
        if len(text) > max_length:
            return text[: max_length - 1] + "…"
        return text

    async def asyncit(self, iterable):
        for i in iterable:
            yield i
            await sleep(0)

    # finds the the pixel to center the text
    async def _center(self, start, end, text, font):
        dist = end - start
        width = font.getsize(text)[0]
        start_pos = start + ((dist - width) / 2)
        return int(start_pos)

    # calculates required exp for next level
    async def _required_exp(self, level: int):
        if level < 0:
            return 0
        return 139 * level + 65

    async def _level_exp(self, level: int):
        return level * 65 + 139 * level * (level - 1) // 2

    async def _find_level(self, total_exp):
        # this is specific to the function above
        return int((1 / 278) * (9 + math.sqrt(81 + 1112 * total_exp)))

    async def char_in_font(self, unicode_char, font):
        for cmap in font["cmap"].tables:
            if cmap.isUnicode():
                if ord(unicode_char) in cmap.cmap:
                    return True
        return False
