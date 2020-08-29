import argparse
import math
import operator

import discord
from redbot.core import commands
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as chat
from tabulate import tabulate

from ..abc import CompositeMetaClass, MixinMeta


class NoExitParser(argparse.ArgumentParser):
    def error(self, message):
        raise commands.BadArgument(message)


class TopParser(commands.Converter):
    page: int
    global_top: bool
    rep: bool

    async def convert(self, ctx, argument):
        parser = NoExitParser(description="top command arguments parser", add_help=False)
        parser.add_argument("page", nargs="?", type=int, default="1")
        parser.add_argument("-g", "--global", dest="global_top", action="store_true")
        parser.add_argument("-r", "--rep", action="store_true")
        return parser.parse_args(argument.split())


class Top(MixinMeta, metaclass=CompositeMetaClass):
    @commands.command(usage="[page] [--global] [--rep]")
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def top(
        self, ctx, *, options: TopParser = argparse.Namespace(page=1, rep=False, global_top=False)
    ):
        """Displays leaderboard.

        Add --rep for reputation.
        Add --global parameter for global. Available only to owner by default."""
        server = ctx.guild
        user = ctx.author
        owner = (
            await self.bot.is_owner(ctx.author)
            if not await self.config.allow_global_top()
            else True
        )

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        async with ctx.typing():
            users = []
            user_stat = []
            is_level = False
            if options.rep and options.global_top and owner:
                title = "Global Rep Leaderboard for {}\n".format(self.bot.user.name)
                async for userinfo in self.db.users.find({}):
                    users.append((userinfo.get("username", userinfo["user_id"]), userinfo["rep"]))

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = [await self._find_global_rep_rank(user), userinfo["rep"]]

                board_type = "Rep"
                icon_url = self.bot.user.avatar_url
            elif options.global_top and owner:
                is_level = True if await self.config.global_levels() else False
                title = "Global Exp Leaderboard for {}\n".format(self.bot.user.name)
                async for userinfo in self.db.users.find({}):
                    if is_level:
                        users.append(
                            (
                                userinfo.get("username", userinfo["user_id"]),
                                userinfo["total_exp"],
                                await self._find_level(userinfo["total_exp"]),
                            )
                        )
                    else:
                        users.append(
                            (userinfo.get("username", userinfo["user_id"]), userinfo["total_exp"])
                        )

                    if str(user.id) == userinfo["user_id"]:
                        if is_level:
                            user_stat = [await self._find_global_rank(user), userinfo["total_exp"]]
                        else:
                            user_stat = [
                                await self._find_global_rank(user),
                                userinfo["total_exp"],
                                await self._find_level(userinfo["total_exp"]),
                            ]

                board_type = "Points"
                icon_url = self.bot.user.avatar_url
            elif options.rep:
                title = "Rep Leaderboard for {}\n".format(server.name)
                async for userinfo in self.db.users.find({}):
                    if userinfo.get("servers", {}).get(str(server.id)):
                        users.append(
                            (userinfo.get("username", userinfo["user_id"]), userinfo["rep"])
                        )

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = [await self._find_global_rep_rank(user), userinfo["rep"]]

                board_type = "Rep"
                icon_url = server.icon_url
            else:
                is_level = True
                title = "Exp Leaderboard for {}\n".format(server.name)
                async for userinfo in self.db.users.find({}):
                    if str(user.id) == userinfo["user_id"]:
                        user_stat = [
                            await self._find_server_rank(user, server),
                            await self._find_server_exp(user, server),
                            userinfo["servers"][str(server.id)]["level"],
                        ]
                    try:
                        if userinfo.get("servers", {}).get(str(server.id)):
                            server_exp = 0
                            for i in range(userinfo["servers"][str(server.id)]["level"]):
                                server_exp += await self._required_exp(i)
                            server_exp += userinfo["servers"][str(server.id)]["current_exp"]
                            users.append(
                                (
                                    userinfo.get("username", userinfo["user_id"]),
                                    server_exp,
                                    userinfo["servers"][str(server.id)]["level"],
                                )
                            )
                    except KeyError:
                        pass
                board_type = "Points"
                icon_url = server.icon_url
            sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

            # multiple page support
            page = options.page
            per_page = 15
            pages = math.ceil(len(sorted_list) / per_page)
            if page > pages:
                page = pages

            msg = ""
            rank = 1 + per_page * (page - 1)
            start_index = per_page * page - per_page
            end_index = per_page * page
            members = []

            async for rank, single_user in AsyncIter(sorted_list[start_index:end_index]).enumerate(
                rank
            ):
                members.append(
                    (rank, single_user[1], single_user[2], single_user[0])
                    if is_level
                    else (rank, single_user[1], single_user[0])
                )
            table = tabulate(
                members,
                headers=["#", board_type, "Level", "Username"]
                if is_level
                else ["#", board_type, "Username"],
                tablefmt="rst",
            )
            table_width = len(table.splitlines()[0])
            msg += "[Page {}/{}]".format(page, pages).rjust(table_width)
            msg += "\n"
            msg += table
            msg += "\n"
            msg += "Your rank: {}\n".format(user_stat[0]).rjust(table_width)
            msg += "{}: {}\n".format(board_type, user_stat[1]).rjust(table_width)
            if is_level:
                msg += "Level: {}\n".format(user_stat[2]).rjust(table_width)

            em = discord.Embed(description=chat.box(msg), colour=user.colour)
            em.set_author(name=title, icon_url=icon_url)

        await ctx.send(embed=em)
