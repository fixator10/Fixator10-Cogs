from argparse import Namespace
from asyncio import sleep
from textwrap import shorten

from redbot.core import commands
from redbot.core.utils import AsyncIter

from ..abc import CompositeMetaClass, MixinMeta
from ..argparsers import TopParser
from ..menus.top import TopMenu, TopPager


class Top(MixinMeta, metaclass=CompositeMetaClass):
    @commands.command(usage="[page] [--global] [--rep] [--server SERVER]")
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def top(
        self,
        ctx,
        *,
        options: TopParser = Namespace(page=1, server=None, rep=False, global_top=False),
    ):
        """Displays leaderboard.

        Add --rep for reputation.
        Add --global parameter for global. Available only to owner by default.
        Add --server <server> parameter to view other's server data. Available only to owner."""
        is_owner = await self.bot.is_owner(ctx.author)
        if options.server and is_owner:
            server = await commands.GuildConverter.convert(ctx, " ".join(options.server))
        else:
            server = ctx.guild
        user = ctx.author
        owner = is_owner if not await self.config.allow_global_top() else True

        async with ctx.typing():
            users = []
            user_stat = []
            is_level = False
            pos = 0
            if options.rep and options.global_top and owner:
                title = "Global Rep Leaderboard for {}\n".format(self.bot.user.name)
                async for userinfo in self.db.users.find({}).allow_disk_use(True).sort("rep", -1):
                    pos += 1
                    users.append(
                        (
                            pos,
                            userinfo["rep"],
                            shorten(
                                userinfo.get("username", userinfo["user_id"]),
                                20,
                                placeholder="\N{HORIZONTAL ELLIPSIS}",
                            ),
                        )
                    )

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = [await self._find_global_rep_rank(user), userinfo["rep"]]
                    await sleep(0)

                board_type = "Rep"
                icon_url = self.bot.user.avatar_url
            elif options.global_top and owner:
                is_level = True if await self.config.global_levels() else False
                title = "Global Exp Leaderboard for {}\n".format(self.bot.user.name)
                async for userinfo in self.db.users.find({}).allow_disk_use(True).sort(
                    "total_exp", -1
                ):
                    pos += 1
                    if is_level:
                        users.append(
                            (
                                pos,
                                userinfo["total_exp"],
                                await self._find_level(userinfo["total_exp"]),
                                shorten(
                                    userinfo.get("username", userinfo["user_id"]),
                                    20,
                                    placeholder="\N{HORIZONTAL ELLIPSIS}",
                                ),
                            )
                        )
                    else:
                        users.append(
                            (
                                pos,
                                userinfo["total_exp"],
                                shorten(
                                    userinfo.get("username", userinfo["user_id"]),
                                    20,
                                    placeholder="\N{HORIZONTAL ELLIPSIS}",
                                ),
                            )
                        )

                    if str(user.id) == userinfo["user_id"]:
                        if is_level:
                            user_stat = [
                                await self._find_global_rank(user),
                                userinfo["total_exp"],
                                await self._find_level(userinfo["total_exp"]),
                            ]
                        else:
                            user_stat = [await self._find_global_rank(user), userinfo["total_exp"]]
                    await sleep(0)

                board_type = "Points"
                icon_url = self.bot.user.avatar_url
            elif options.rep:
                title = "Rep Leaderboard for {}\n".format(server.name)
                async for userinfo in self.db.users.find(
                    {f"servers.{server.id}": {"$exists": True}}
                ).allow_disk_use(True).sort("rep", -1):
                    pos += 1
                    users.append(
                        (
                            pos,
                            userinfo["rep"],
                            shorten(
                                userinfo.get("username", userinfo["user_id"]),
                                20,
                                placeholder="\N{HORIZONTAL ELLIPSIS}",
                            ),
                        )
                    )

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = [
                            await self._find_server_rep_rank(user, server),
                            userinfo["rep"],
                        ]
                    await sleep(0)

                board_type = "Rep"
                icon_url = server.icon_url
            else:
                is_level = True
                title = "Exp Leaderboard for {}\n".format(server.name)
                async for userinfo in self.db.users.find(
                    {f"servers.{server.id}": {"$exists": True}}
                ).allow_disk_use(True).sort(
                    [(f"servers.{server.id}.level", -1), (f"servers.{server.id}.current_exp", -1)]
                ):
                    pos += 1
                    if str(user.id) == userinfo["user_id"]:
                        user_stat = [
                            await self._find_server_rank(user, server),
                            await self._find_server_exp(user, server),
                            userinfo["servers"].get(str(server.id), {}).get("level"),
                        ]
                    if userinfo.get("servers", {}).get(str(server.id)):
                        server_exp = 0
                        async for i in AsyncIter(
                            range(userinfo["servers"][str(server.id)].get("level", 0))
                        ):
                            server_exp += await self._required_exp(i)
                        server_exp += userinfo["servers"][str(server.id)].get("current_exp", 0)
                        users.append(
                            (
                                pos,
                                server_exp,
                                userinfo["servers"][str(server.id)].get("level", 0),
                                shorten(
                                    userinfo.get("username", userinfo["user_id"]),
                                    20,
                                    placeholder="\N{HORIZONTAL ELLIPSIS}",
                                ),
                            )
                        )
                    await sleep(0)
                board_type = "Points"
                icon_url = server.icon_url

            pages = TopPager(users, board_type, is_level, user_stat, icon_url, title)
            menu = TopMenu(pages)
            await menu.start(ctx)
            page = options.page
            if page > pages.get_max_pages():
                page = pages.get_max_pages()
            if page < 1:
                page = 1
            await menu.show_page(page - 1)
