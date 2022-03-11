from abc import ABC
from asyncio import TimeoutError as AsyncTimeoutError
from typing import Optional

import discord
from redbot.core import bank, commands
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.predicates import MessagePredicate

from leveler.abc import MixinMeta
from leveler.menus.badges import AvailableBadgePager, BadgeMenu, OwnBadgePager

from .basecmd import LevelSetBaseCMD


class Badge(MixinMeta, ABC):
    """Badge commands"""

    lvlset = getattr(LevelSetBaseCMD, "lvlset")

    @lvlset.group(name="badge")
    async def lvlset_badge(self, ctx):
        """Badge Configuration Options."""

    @lvlset_badge.command(name="available", aliases=["shop"])
    @commands.guild_only()
    async def badges_available(self, ctx, global_badges: bool = False):
        """Get a list of available badges."""
        server = ctx.guild
        if global_badges:
            servername = "Global"
            icon_url = self.bot.user.avatar_url
            serverid = "global"
        else:
            servername = server.name
            icon_url = server.icon_url
            serverid = server.id
        server_badges = await self.db.badges.find_one({"server_id": str(serverid)})
        if server_badges and (server_badges := server_badges["badges"]):
            await BadgeMenu(
                AvailableBadgePager(list(server_badges.values()), servername, serverid, icon_url),
                can_buy=True,
            ).start(ctx)
        else:
            await ctx.send(chat.info("There is no badges available."))

    @lvlset_badge.command(name="list")
    @commands.guild_only()
    async def listuserbadges(self, ctx, user: discord.Member = None):
        """Get all badges of a user."""
        if user is None:
            user = ctx.author
        if user.bot:
            await ctx.send_help()
            return
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if badges := userinfo["badges"]:
            await BadgeMenu(OwnBadgePager(list(badges.values()), user)).start(ctx)
        else:
            await ctx.send(chat.info("You have no badges."))

    @lvlset_badge.command(name="buy")
    @commands.guild_only()
    async def buy_badge(self, ctx, is_global: Optional[bool], *, name: str):
        """Buy a badge."""
        user = ctx.author
        server = ctx.guild
        serverid = "global" if is_global else server.id
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)
        server_badge_info = await self.db.badges.find_one({"server_id": str(serverid)})

        if server_badge_info:
            server_badges = server_badge_info["badges"]
            if name in server_badges:
                if "{}_{}".format(name, str(serverid)) not in userinfo["badges"].keys():
                    badge_info = server_badges[name]
                    if badge_info["price"] == -1:
                        await ctx.send("That badge is not purchasable.")
                    elif badge_info["price"] == 0:
                        userinfo["badges"]["{}_{}".format(name, str(serverid))] = server_badges[
                            name
                        ]
                        await self.db.users.update_one(
                            {"user_id": userinfo["user_id"]},
                            {"$set": {"badges": userinfo["badges"]}},
                        )
                        await ctx.send(
                            "`{}` has been obtained.\n"
                            "You can set it on your profile by using `{}lvlset badge set`.".format(
                                name, ctx.clean_prefix
                            )
                        )
                    else:
                        await ctx.send(
                            "{}, you are about to buy the `{}` badge for `{}`. Confirm by typing `yes`.".format(
                                user.mention, name, badge_info["price"]
                            ),
                            allowed_mentions=discord.AllowedMentions(
                                users=await self.config.mention()
                            ),
                        )
                        pred = MessagePredicate.yes_or_no(ctx)
                        try:
                            await self.bot.wait_for("message", timeout=15, check=pred)
                        except AsyncTimeoutError:
                            pass
                        if not pred.result:
                            await ctx.send("Purchase canceled.")
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
                                "You have bought the `{}` badge for `{}`.\n"
                                "You can set it on your profile by using `{}lvlset badge set`.".format(
                                    name, badge_info["price"], ctx.clean_prefix
                                )
                            )
                        elif await bank.get_balance(user) < badge_info["price"]:
                            await ctx.send(
                                "Not enough money! Need `{}` more.".format(
                                    badge_info["price"] - await bank.get_balance(user)
                                )
                            )
                else:
                    await ctx.send("{}, you already have this badge!".format(user.name))
            else:
                await ctx.send(
                    "The badge `{}` does not exist. Check `{}lvlset badge available`".format(
                        name, ctx.clean_prefix
                    )
                )
        else:
            await ctx.send(
                "There are no badges to get! "
                "You can try to buy global badge via `{}lvlset badge buy True {}`".format(
                    ctx.clean_prefix, name
                )
            )

    @lvlset_badge.command(name="set")
    @commands.guild_only()
    async def set_badge(self, ctx, name: str, priority_num: int):
        """Set a badge to profile.

        Options for priority number :
        `-1`: The badge will be invisible.
        `0`: The badge won't be show on your profile.
        Maximum to `5000`."""
        user = ctx.author

        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if priority_num < -1 or priority_num > 5000:
            await ctx.send("Invalid priority number! -1-5000")
            return

        for badge in userinfo["badges"]:
            if userinfo["badges"][badge]["badge_name"] == name:
                userinfo["badges"][badge]["priority_num"] = priority_num
                await self.db.users.update_one(
                    {"user_id": userinfo["user_id"]},
                    {"$set": {"badges": userinfo["badges"]}},
                )
                await ctx.send(
                    "The `{}` badge priority has been set to `{}`!".format(
                        userinfo["badges"][badge]["badge_name"], priority_num
                    )
                )
                break
        else:
            await ctx.send("You don't have that badge!")
