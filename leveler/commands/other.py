import time

import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting as chat

from ..abc import CompositeMetaClass, MixinMeta
from ..menus.backgrounds import BackgroundMenu, BackgroundPager


class Other(MixinMeta, metaclass=CompositeMetaClass):
    """Other commands"""

    @commands.command()
    @commands.guild_only()
    async def rep(self, ctx, *, user: discord.Member = None):
        """Gives a reputation point to a designated player."""
        org_user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        if user:
            await self._create_user(user, server)
        org_userinfo = await self.db.users.find_one({"user_id": str(org_user.id)})
        curr_time = time.time()

        if user and user.id == org_user.id:
            await ctx.send("You can't give a rep to yourself!")
            return
        if user and user.bot:
            await ctx.send("You can't give a rep to a bot!")
            return
        if user and await self.config.rep_rotation() and user.id == org_userinfo.get("lastrep"):
            await ctx.send("You already gave a rep point to this user!")
            return

        delta = float(curr_time) - float(org_userinfo.get("rep_block", 0))
        if user and delta >= 43200.0 and delta > 0:
            userinfo = await self.db.users.find_one({"user_id": str(user.id)})
            await self.db.users.update_one(
                {"user_id": str(org_user.id)}, {"$set": {"lastrep": user.id}}
            )
            await self.db.users.update_one(
                {"user_id": str(org_user.id)}, {"$set": {"rep_block": curr_time}}
            )
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"rep": userinfo["rep"] + 1}}
            )
            await ctx.send(
                "You have just given {} a reputation point!".format(user.mention),
                allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
            )
        else:
            # calulate time left
            seconds = 43200 - delta
            if seconds < 0:
                await ctx.send("You can give a rep!")
                return
            await ctx.send(
                "You need to wait {} until you can give reputation again!".format(
                    chat.humanize_timedelta(seconds=seconds)
                )
            )

    @commands.command(name="backgrounds", usage="[profile|rank|levelup]")
    @commands.guild_only()
    async def list_backgrounds(self, ctx, bg_type: str = "profile"):
        """Gives a list of backgrounds."""
        backgrounds = await self.config.backgrounds()
        pages = {t: BackgroundPager(tuple(backgrounds[t].items())) for t in backgrounds}
        bg_type = bg_type.casefold()
        if bg_type not in pages:
            await ctx.send(
                chat.error("Unknown background type. It should be one of: {}.").format(
                    chat.humanize_list(tuple(pages.keys()), style="or")
                )
            )
            return
        await BackgroundMenu(pages, bg_type).start(ctx)
