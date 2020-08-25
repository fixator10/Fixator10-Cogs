import argparse
import math
import operator

import discord
from redbot.core import commands
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as chat

from ..abc import CompositeMetaClass, MixinMeta


class NoExitParser(argparse.ArgumentParser):
    def error(self, message):
        raise commands.BadArgument(message)


class TopParser(commands.Converter):
    async def convert(self, ctx, argument):
        parser = NoExitParser(description="top command arguments parser", add_help=False)
        parser.add_argument("page", nargs="?", type=int, default="1")
        parser.add_argument("-g", "--global", dest="global_top", action="store_true")
        parser.add_argument("-r", "--rep", action="store_true")
        return parser.parse_args(argument.split())


class Top(MixinMeta, metaclass=CompositeMetaClass):
    @commands.command(usage="[page] [--global] [--rep]")
    @commands.guild_only()
    async def top(self, ctx, *, options: TopParser = None):
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
        await self._create_user(user, server)
        # TODO: Add a settings command for this
        if options is None:
            options = argparse.Namespace(page=1, rep=False, global_top=False)

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        async with ctx.typing():
            users = []
            user_stat = None
            if options.rep and options.global_top and owner:
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
            elif options.global_top and owner:
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
            elif options.rep:
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
            page = options.page
            per_page = 15
            pages = math.ceil(len(sorted_list) / per_page)
            if page > pages:
                page = pages

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
