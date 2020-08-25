import time

import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting as chat

from ..abc import CompositeMetaClass, MixinMeta


class Other(MixinMeta, CompositeMetaClass):
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
