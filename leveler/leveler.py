import math
import operator
import random
import time
from abc import ABC
from logging import getLogger
from asyncio import TimeoutError as AsyncTimeoutError
from collections import OrderedDict
from datetime import timedelta
from tabulate import tabulate
from typing import Union

import aiohttp
import discord
from redbot.core import bank
from redbot.core import checks
from redbot.core import commands
from redbot.core import Config
from redbot.core.bot import Red
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core.utils.predicates import MessagePredicate

try:
    import numpy
    from scipy import cluster
except Exception as e:
    print(
        f"{__file__}: numpy/scipy is unable to import: {e}\nAutocolor feature will be unavailable"
    )

from .mongodb import MongoDB
from .exp import XP
from .db_converters import DBConverters
from .image_generators import ImageGenerators
from .utils import Utils


# noinspection PyUnusedLocal
async def non_global_bank(ctx):
    return not await bank.is_global()


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """
    This allows the metaclass used for proper type detection to
    coexist with discord.py's metaclass
    """

    pass


class Leveler(
    MongoDB, XP, DBConverters, ImageGenerators, Utils, commands.Cog, metaclass=CompositeMetaClass
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

    def cog_unload(self):
        self.session.detach()
        self._disconnect_mongo()

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
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        # check if disabled
        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            em = await self.profile_text(user, server, userinfo)
            await channel.send(embed=em)
        else:
            async with ctx.channel.typing():
                profile = await self.draw_profile(user, server)
                file = discord.File(profile, filename="profile.png")
                await channel.send(
                    "**User profile for {}**".format(await self._is_mention(user)), file=file,
                )
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"profile_block": curr_time}}, upsert=True,
            )

    async def profile_text(self, user, server, userinfo):
        em = discord.Embed(colour=user.colour)
        em.add_field(name="Title:", value=userinfo["title"] or None)
        em.add_field(name="Reps:", value=userinfo["rep"])
        em.add_field(name="Global Rank:", value="#{}".format(await self._find_global_rank(user)))
        em.add_field(
            name="Server Rank:", value="#{}".format(await self._find_server_rank(user, server)),
        )
        em.add_field(
            name="Server Level:", value=format(userinfo["servers"][str(server.id)]["level"]),
        )
        em.add_field(name="Total Exp:", value=userinfo["total_exp"])
        em.add_field(name="Server Exp:", value=await self._find_server_exp(user, server))
        u_credits = await bank.get_balance(user)
        em.add_field(
            name="Credits:", value=f"{u_credits}{(await bank.get_currency_name(server))[0]}",
        )
        em.add_field(name="Info:", value=userinfo["info"] or None)
        em.add_field(
            name="Badges:", value=(", ".join(userinfo["badges"]).replace("_", " ") or None),
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
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

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
                    "**Ranking & Statistics for {}**".format(await self._is_mention(user)),
                    file=file,
                )
            await self.db.users.update_one(
                {"user_id": str(user.id)},
                {"$set": {"rank_block".format(server.id): curr_time}},
                upsert=True,
            )

    async def rank_text(self, user, server, userinfo):
        em = discord.Embed(colour=user.colour)
        em.add_field(
            name="Server Rank", value="#{}".format(await self._find_server_rank(user, server)),
        )
        em.add_field(name="Reps", value=userinfo["rep"])
        em.add_field(name="Server Level", value=userinfo["servers"][str(server.id)]["level"])
        em.add_field(name="Server Exp", value=await self._find_server_exp(user, server))
        em.set_author(name="Rank & Statistics for {}".format(user.name), url=user.avatar_url)
        em.set_thumbnail(url=user.avatar_url)
        return em

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
                async for userinfo in self.db.users.find({}):
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
                async for userinfo in self.db.users.find({}):
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
                async for userinfo in self.db.users.find({}):
                    if "servers" in userinfo and str(server.id) in userinfo["servers"]:
                        try:
                            users.append((userinfo["username"], userinfo["rep"]))
                        except KeyError:
                            users.append((userinfo["user_id"], userinfo["rep"]))

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = userinfo["rep"]

                board_type = "Rep"
                footer_text = "Your Rank: {}                  {}: {}".format(
                    await self._find_server_rep_rank(user, server), board_type, user_stat,
                )
                icon_url = server.icon_url
            else:
                title = "Exp Leaderboard for {}\n".format(server.name)
                async for userinfo in self.db.users.find({}):
                    try:
                        if "servers" in userinfo and str(server.id) in userinfo["servers"]:
                            server_exp = 0
                            for i in range(userinfo["servers"][str(server.id)]["level"]):
                                server_exp += await self._required_exp(i)
                            server_exp += userinfo["servers"][str(server.id)]["current_exp"]
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
                            "**Please enter a valid page number! (1 - {})**".format(str(pages))
                        )
                        return
                    break

            msg = ""
            msg += "Rank     Name                   (Page {}/{})     \n\n".format(page, pages)
            rank = 1 + per_page * (page - 1)
            start_index = per_page * page - per_page
            end_index = per_page * page

            default_label = "   "
            special_labels = ["♔", "♕", "♖", "♗", "♘", "♙"]

            async for single_user in AsyncIter(sorted_list[start_index:end_index]):
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
            em.description = chat.box(msg)

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
        org_userinfo = await self.db.users.find_one({"user_id": str(org_user.id)})
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
            userinfo = await self.db.users.find_one({"user_id": str(user.id)})
            await self.db.users.update_one(
                {"user_id": str(org_user.id)}, {"$set": {"rep_block": curr_time}}
            )
            await self.db.users.update_one(
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
            await ctx.send(
                "**You need to wait {} until you can give reputation again!**".format(
                    chat.humanize_timedelta(seconds=seconds)
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
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

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
            msg += "Rep section color: {}\n".format(self._rgb_to_hex(userinfo["rep_color"]))
        if "badge_col_color" in userinfo.keys() and userinfo["badge_col_color"]:
            msg += "Badge section color: {}\n".format(
                self._rgb_to_hex(userinfo["badge_col_color"])
            )
        if "rank_info_color" in userinfo.keys() and userinfo["rank_info_color"]:
            msg += "Rank info color: {}\n".format(self._rgb_to_hex(userinfo["rank_info_color"]))
        if "rank_exp_color" in userinfo.keys() and userinfo["rank_exp_color"]:
            msg += "Rank exp color: {}\n".format(self._rgb_to_hex(userinfo["rank_exp_color"]))
        if "levelup_info_color" in userinfo.keys() and userinfo["levelup_info_color"]:
            msg += "Level info color: {}\n".format(
                self._rgb_to_hex(userinfo["levelup_info_color"])
            )
        msg += "Badges: "
        msg += ", ".join(userinfo["badges"])

        em = discord.Embed(description=msg, colour=user.colour)
        em.set_author(
            name="Profile Information for {}".format(user.name), icon_url=user.avatar_url,
        )
        await ctx.send(embed=em)

    @checks.is_owner()
    @commands.group()
    async def levelerset(self, ctx):
        """
        MongoDB server configuration options.
        
        Use that command in DM to see current settings.
        """
        if not ctx.invoked_subcommand and ctx.channel.type == discord.ChannelType.private:
            settings = [
                (setting.replace("_", " ").title(), value)
                for setting, value in (await self.config.custom("MONGODB").get_raw()).items()
                if value
            ]
            await ctx.send(chat.box(tabulate(settings, tablefmt="plain")))

    @levelerset.command()
    async def host(self, ctx, host: str = "localhost"):
        """Set the MongoDB server host."""
        await self.config.custom("MONGODB").host.set(host)
        message = await ctx.send(
            f"MongoDB host set to {host}.\nNow trying to connect to the new host..."
        )
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect to the new host...", "")
                + "Failed to connect. Please try again with a valid host."
            )
        await message.edit(
            content=message.content.replace("Now trying to connect to the new host...", "")
        )

    @levelerset.command()
    async def port(self, ctx, port: int = 27017):
        """Set the MongoDB server port."""
        await self.config.custom("MONGODB").port.set(port)
        message = await ctx.send(
            f"MongoDB port set to {port}.\nNow trying to connect to the new port..."
        )
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect to the new port...", "")
                + "Failed to connect. Please try again with a valid port."
            )
        await message.edit(
            content=message.content.replace("Now trying to connect to the new port...", "")
        )

    @levelerset.command(aliases=["creds"])
    async def credentials(self, ctx, username: str = None, password: str = None):
        """Set the MongoDB server credentials."""
        await self.config.custom("MONGODB").username.set(username)
        await self.config.custom("MONGODB").password.set(password)
        message = await ctx.send("MongoDB credentials set.\nNow trying to connect...")
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect...", "")
                + "Failed to connect. Please try again with valid credentials."
            )
        await message.edit(content=message.content.replace("Now trying to connect...", ""))

    @levelerset.command()
    async def dbname(self, ctx, dbname: str = "leveler"):
        """Set the MongoDB db name."""
        await self.config.custom("MONGODB").db_name.set(dbname)
        message = await ctx.send("MongoDB db name set.\nNow trying to connect...")
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect...", "")
                + "Failed to connect. Please try again with a valid db name."
            )
        await message.edit(content=message.content.replace("Now trying to connect...", ""))

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
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
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
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
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

    @checks.admin_or_permissions(manage_guild=True)
    @commands.group()
    @commands.guild_only()
    async def lvladmin(self, ctx):
        """Admin options features."""
        pass

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command()
    async def overview(self, ctx):
        """A list of settings."""
        num_users = len(await self.db.users.find({}).to_list(None))
        is_owner = await self.bot.is_owner(ctx.author)

        em = discord.Embed(colour=await ctx.embed_color())
        msg = ""
        msg += "**Enabled:** {}\n".format(
            self.bool_emojify(not await self.config.guild(ctx.guild).disabled())
        )
        msg += "**Unique Users:** {}\n".format(num_users)
        if is_owner:
            msg += "**Mentions:** {}\n".format(self.bool_emojify(await self.config.mention()))
        if bg_price := await self.config.bg_price():
            msg += "**Background Price:** {}\n".format(bg_price)
        if is_owner:
            msg += "**Badge type:** {}\n".format(await self.config.badge_type())
        msg += "**Enabled Level Messages:** {}\n".format(
            self.bool_emojify(await self.config.guild(ctx.guild).lvl_msg())
        )
        msg += "**Private Level Messages:** {}\n".format(
            self.bool_emojify(await self.config.guild(ctx.guild).private_lvl_message())
        )
        if lvl_lock := await self.config.guild(ctx.guild).lvl_msg_lock():
            msg += "**Level Messages Channel:** {}\n".format(
                ctx.guild.get_channel(lvl_lock).mention
            )
        em.set_author(name="Settings Overview for {}".format(ctx.guild.name))
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
                "**Ignored channels:** \n" + ("\n".join(channels) or "No ignored channels set")
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
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

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

        await self.db.users.update_one(
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
            "**{}'s Level has been set to `{}`.**".format(await self._is_mention(user), level)
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
                await ctx.send(
                    "I was unable to get data about user with ID `{}`. Try again later.".format(
                        user
                    )
                )
                return
        if user is None:
            await ctx.send_help()
            return
        chat_block = time.time() + timedelta(days=days).total_seconds()
        try:
            await self.db.users.update_one(
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
            await ctx.send("**Text-only messages disabled for `{}`.**".format(server.name))
        else:
            await self.config.guild(server).text_only.set(True)
            await ctx.send("**Text-only messages enabled for `{}`.**".format(server.name))

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
            await ctx.send("**Private level-up alerts disabled for `{}`.**".format(server.name))
        else:
            await self.config.guild(server).private_lvl_message.set(True)
            await ctx.send("**Private level-up alerts enabled for `{}`.**".format(server.name))

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
        await ctx.send(f"XP given has been set to a range of {min_xp} to {max_xp} XP per message.")

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
        await self._create_user(user, server)
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
        await self._create_user(user, server)
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
        await self._create_user(user, server)

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
        """Define if badge must be circle or bars."""
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

        # creates user if doesn't exist
        await self._create_user(user, server)

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
        await self._create_user(user, server)
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
        # creates user if doesn't exist
        await self._create_user(user, server)
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
    async def linkrole(
        self, ctx, add_role: discord.Role, level: int, remove_role: discord.Role = None
    ):
        """Associate a role with a level.

        Removes previous role if given."""
        server = ctx.guild

        server_roles = await self.db.roles.find_one({"server_id": str(server.id)})
        if not server_roles:
            new_server = {
                "server_id": str(server.id),
                "roles": {
                    add_role.name: {
                        "level": str(level),
                        "remove_role": remove_role.name if remove_role else None,
                    }
                },
            }
            await self.db.roles.insert_one(new_server)
        else:
            if add_role.name not in server_roles["roles"]:
                server_roles["roles"][add_role.name] = {}

            server_roles["roles"][add_role.name]["level"] = str(level)
            server_roles["roles"][add_role.name]["remove_role"] = (
                remove_role.name if remove_role else None
            )
            await self.db.roles.update_one(
                {"server_id": str(server.id)}, {"$set": {"roles": server_roles["roles"]}},
            )

        if remove_role:
            await ctx.send(
                "**The `{}` role has been linked to level `{}`. "
                "Will also remove `{}` role.**".format(add_role, level, remove_role)
            )
        else:
            await ctx.send(
                "**The `{}` role has been linked to level `{}`**".format(add_role, level)
            )

    @checks.mod_or_permissions(manage_roles=True)
    @role.command(name="unlink", usage="<role>")
    @commands.guild_only()
    async def unlinkrole(self, ctx, *, role_to_unlink: discord.Role):
        """Delete a role/level association."""
        server = ctx.guild

        server_roles = await self.db.roles.find_one({"server_id": str(server.id)})
        roles = server_roles["roles"]

        if role_to_unlink.name in roles:
            await ctx.send(
                "**Role/Level association `{}`/`{}` removed.**".format(
                    role_to_unlink.name, roles[role_to_unlink.name]["level"]
                )
            )
            del roles[role_to_unlink.name]
            await self.db.roles.update_one(
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

        server_roles = await self.db.roles.find_one({"server_id": str(server.id)})

        em = discord.Embed(colour=await ctx.embed_color())
        em.set_author(
            name="Current Role - Level Links for {}".format(server.name), icon_url=server.icon_url,
        )

        if server_roles is None or not server_roles.get("roles"):
            msg = "None"
        else:
            sortorder = sorted(
                server_roles["roles"], key=lambda r: int(server_roles["roles"][r]["level"]),
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
            await ctx.send("**Please choose a valid type. Must be `profile`, `rank` or `levelup`.")
            return

        # test if valid user_id
        userinfo = await self.db.users.find_one({"user_id": str(user_id)})
        if not userinfo:
            await ctx.send("**That is not a valid user id!**")
            return

        if not await self._valid_image_url(img_url):
            await ctx.send("**That is not a valid image URL!**")
            return

        await self.db.users.update_one(
            {"user_id": str(user_id)}, {"$set": {"{}_background".format(type_input): img_url}},
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
            await ctx.send("**The profile background(`{}`) has been deleted.**".format(name))
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
            await ctx.send("**The rank background(`{}`) has been deleted.**".format(name))
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
            await ctx.send("**The level-up background(`{}`) has been deleted.**".format(name))
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
