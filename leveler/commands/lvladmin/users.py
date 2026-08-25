import asyncio
import time
from typing import Union

import discord
from redbot.core import commands

from leveler.abc import MixinMeta

from .basecmd import LevelAdminBaseCMD


class Users(MixinMeta):
    """User-related administration commands"""

    lvladmin = getattr(LevelAdminBaseCMD, "lvladmin")

    @commands.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def xpban(
        self,
        ctx,
        bantime: commands.converter.TimedeltaConverter(default_unit="seconds"),
        *,
        user: Union[discord.User, int],
    ):
        """Ban user from getting experience."""
        if isinstance(user, int):
            userinfo = await self.db.users.find_one({"user_id": str(user)})
            if not userinfo:
                await ctx.send("Discord user with ID `{}` not found.".format(user))
                return
            user = discord.Object(user)
        chat_block = time.time() + bantime.total_seconds()
        try:
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"chat_block": chat_block}}
            )
        except Exception as exc:
            await ctx.send("Unable to add chat block: {}".format(exc))
        else:
            await ctx.tick()

    @commands.admin_or_permissions(manage_guild=True)
    @lvladmin.command()
    @commands.guild_only()
    async def resetranks(self, ctx: commands.Context):
        """
        Reset everyone's xp and level to zero.

        Roles will be fixed when the user next would earn exp.
        """
        main_msg = "Fixing members {current}/{total}"
        msg = await ctx.send(main_msg.format(current=0, total=len(ctx.guild.members)))
        current = 0
        async with ctx.typing():
            for member in ctx.guild.members:
                if member.bot:
                    continue
                userinfo = await self.db.users.find_one({"user_id": str(member.id)})
                if userinfo is None:
                    # no point fixing users who have not been created yet, they might never speak!
                    continue
                total_exp = userinfo["total_exp"] - userinfo.get(str(ctx.guild.id), {}).get(
                    "current_exp", 0
                )
                await self.db.users.update_one(
                    {"user_id": str(member.id)},
                    {
                        "$set": {
                            "servers.{}.level".format(ctx.guild.id): 0,
                            "servers.{}.current_exp".format(ctx.guild.id): 0,
                            "total_exp": total_exp,
                        }
                    },
                )
                current += 1
                if current % 100 == 0:
                    await msg.edit(
                        content=main_msg.format(current=0, total=len(ctx.guild.members))
                    )
                    await asyncio.sleep(5)
        await ctx.send(
            "Finished resetting everyone's experience and levels. Roles will be reset automatically the next time they would earn exp."
        )

    @commands.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def setlevel(self, ctx, user: discord.Member, level: int):
        """Set a user's level manually."""
        server = ctx.guild
        channel = ctx.channel
        if user.bot:
            await ctx.send_help()
            return
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        if level < 0:
            await ctx.send("Please enter a positive number.")
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
            "{}'s Level has been set to `{}`.".format(user.mention, level),
            allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
        )
        await self._handle_levelup(user, userinfo, server, channel)
