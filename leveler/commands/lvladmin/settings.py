from functools import partial

import discord
from redbot.core import checks, commands
from redbot.core.utils import chat_formatting as chat
from tabulate import tabulate

from leveler.abc import MixinMeta

from .basecmd import LevelAdminBaseCMD

tabulate_settings = partial(tabulate, headers=["Setting", "Value"], tablefmt="presto")


class Settings(MixinMeta):
    """Setting administration commands"""

    lvladmin = getattr(LevelAdminBaseCMD, "lvladmin")

    @lvladmin.command()
    async def overview(self, ctx):
        """A list of settings."""
        is_owner = await self.bot.is_owner(ctx.author)

        em = discord.Embed(colour=await ctx.embed_color())
        settings = {
            "Text only mode": self.bool_emojify(await self.config.guild(ctx.guild).text_only()),
            "Level messages enabled": self.bool_emojify(
                await self.config.guild(ctx.guild).lvl_msg()
            ),
            "Level messages are private": self.bool_emojify(
                await self.config.guild(ctx.guild).private_lvl_message()
            ),
        }
        owner_settings = {}
        if is_owner:
            owner_settings.update(
                {
                    "Unique registered users": str(await self.db.users.count_documents({})),
                    "XP per message": "{}-{}".format(*await self.config.xp()),
                    "Min message length": str(await self.config.message_length()),
                    "Global top": self.bool_emojify(await self.config.allow_global_top()),
                    "Mentions": self.bool_emojify(await self.config.mention()),
                    "Rep users rotation": self.bool_emojify(await self.config.rep_rotation()),
                    "Badges type": await self.config.badge_type(),
                }
            )
        if lvl_lock_channel := ctx.guild.get_channel(
            await self.config.guild(ctx.guild).lvl_msg_lock()
        ):
            settings["Level messages channel lock"] = f"#{lvl_lock_channel.name}"
        if msg_credits := await self.config.guild(ctx.guild).msg_credits():
            settings["Currency per message"] = msg_credits
        if is_owner and (bg_price := await self.config.bg_price()):
            owner_settings["Background price"] = bg_price
        em.description = chat.box(tabulate_settings(settings.items())) + (
            chat.box(tabulate_settings(owner_settings.items())) if owner_settings else ""
        )
        em.set_author(
            name="Settings Overview for {}".format(ctx.guild.name), icon_url=ctx.guild.icon_url
        )
        await ctx.send(embed=em)

    @checks.is_owner()
    @lvladmin.command()
    async def resetrep(self, ctx):
        """Resets all reputation points from MonogoDB"""
        async with ctx.typing():
            await self.db.users.update_many({}, {"$set": {"rep": 0}})
            await ctx.send("All reputation points have been removed.")

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
                "Ignored channels: \n" + ("\n".join(channels) or "No ignored channels set")
            )
            return
        if channel.id in await self.config.guild(server).ignored_channels():
            async with self.config.guild(server).ignored_channels() as channels:
                channels.remove(channel.id)
            await ctx.send(f"Messages in {channel.mention} will give exp now.")
        else:
            async with self.config.guild(server).ignored_channels() as channels:
                channels.append(channel.id)
            await ctx.send(f"Messages in {channel.mention} will not give exp now.")

    @commands.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def mention(self, ctx):
        """Toggle mentions on messages."""
        if await self.config.mention():
            await self.config.mention.set(False)
            await ctx.send("Mentions disabled.")
        else:
            await self.config.mention.set(True)
            await ctx.send("Mentions enabled.")

    @lvladmin.command()
    @commands.guild_only()
    async def textonly(self, ctx):
        """Toggle text-based messages on the server."""
        server = ctx.guild
        if await self.config.guild(server).text_only():
            await self.config.guild(server).text_only.set(False)
            await ctx.send("Text-only messages disabled for `{}`.".format(server.name))
        else:
            await self.config.guild(server).text_only.set(True)
            await ctx.send("Text-only messages enabled for `{}`.".format(server.name))

    @lvladmin.command(name="alerts")
    @commands.guild_only()
    async def lvlalert(self, ctx):
        """Toggle level-up messages on the server."""
        server = ctx.guild

        if await self.config.guild(server).lvl_msg():
            await self.config.guild(server).lvl_msg.set(False)
            await ctx.send("Level-up alerts disabled for `{}`.".format(server.name))
        else:
            await self.config.guild(server).lvl_msg.set(True)
            await ctx.send("Level-up alerts enabled for `{}`.".format(server.name))

    @lvladmin.command(name="private")
    @commands.guild_only()
    async def lvlprivate(self, ctx):
        """Toggles level-up alert in private message to the user."""
        server = ctx.guild
        if await self.config.guild(server).private_lvl_message():
            await self.config.guild(server).private_lvl_message.set(False)
            await ctx.send("Private level-up alerts disabled for `{}`.".format(server.name))
        else:
            await self.config.guild(server).private_lvl_message.set(True)
            await ctx.send("Private level-up alerts enabled for `{}`.".format(server.name))

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def reprotation(self, ctx):
        """Toggles rep rotation.

        Forces users to change target for rep each time.
        """
        if await self.config.rep_rotation():
            await self.config.rep_rotation.set(False)
            await ctx.send("Rep rotation is disabled.")
        else:
            await self.config.rep_rotation.set(True)
            await ctx.send("Rep rotation is enabled.")

    @lvladmin.command(aliases=["exp"])
    @commands.is_owner()
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
    @commands.is_owner()
    async def length(self, ctx, message_length: int = 10):
        """Set minimum message length for XP gain.

        Messages with attachments will give XP regardless of length"""
        if message_length < 0:
            raise commands.BadArgument
        await self.config.message_length.set(message_length)
        await ctx.tick()

    @lvladmin.command(name="globaltop")
    @commands.is_owner()
    async def allow_global_top(self, ctx):
        """Allow usage of `--global` argument in `[p]top` command"""
        # Reason: https://support-dev.discord.com/hc/en-us/articles/360043053492
        server = ctx.guild
        if await self.config.allow_global_top():
            await self.config.allow_global_top.set(False)
            await ctx.send(
                "`--global` argument is now available only to owner.".format(server.name)
            )
        else:
            await self.config.allow_global_top.set(True)
            await ctx.send("`--global` argument is now available to everyone.".format(server.name))

    @lvladmin.command()
    @commands.is_owner()
    async def globallevels(self, ctx):
        """Show levels in global leaderboard.

        This may significantly increase leaderboard loading times and the bot's CPU and RAM usage."""
        server = ctx.guild
        if await self.config.global_levels():
            await self.config.global_levels.set(False)
            await ctx.send(
                "Levels will be not included in global leaderboard now.".format(server.name)
            )
        else:
            await self.config.global_levels.set(True)
            await ctx.send(
                "Levels will be included in global leaderboard now.".format(server.name)
            )

    @lvladmin.command(name="lock")
    @commands.guild_only()
    async def lvlmsglock(self, ctx):
        """Locks levelup messages to one channel.

        Disable command via locked channel."""
        channel = ctx.channel
        server = ctx.guild

        if channel.id == await self.config.guild(server).lvl_msg_lock():
            await self.config.guild(server).lvl_msg_lock.set(None)
            await ctx.send("Level-up message lock disabled.")
        else:
            await self.config.guild(server).lvl_msg_lock.set(channel.id)
            await ctx.send("Level-up messages locked to `#{}`".format(channel.name))
