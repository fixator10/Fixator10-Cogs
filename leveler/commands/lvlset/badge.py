import operator
from abc import ABC
from asyncio import TimeoutError as AsyncTimeoutError

import discord
from redbot.core import bank, commands
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate

from leveler.abc import MixinMeta

from .basecmd import LevelSetBaseCMD


class Badge(MixinMeta, ABC):
    """Badge commands"""

    lvlset = getattr(LevelSetBaseCMD, "lvlset")

    @lvlset.group(name="badge")
    async def lvlset_badge(self, ctx):
        """Badge Configuration Options."""

    @lvlset_badge.command()
    @commands.guild_only()
    async def available(self, ctx, global_badges: bool = False):
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

    @lvlset_badge.command(name="buy")
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
