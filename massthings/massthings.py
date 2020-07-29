from asyncio import sleep
from collections import Counter
from typing import Union

import discord
from redbot.core import checks, commands
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.mod import get_audit_reason
from redbot.core.utils.predicates import MessagePredicate
from tabulate import tabulate

_ = Translator("MassThings", __file__)


@cog_i18n(_)
class MassThings(commands.Cog, command_attrs={"hidden": True}):
    """Cog for doing things in bulk.

    May be against Discord API terms. Use with caution.
    I'm not responsible for any aftermath of using this cog."""

    __version__ = "1.0.0"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xE697CB2922F944ADA39D51640C27606F)
        self.aware_of_shit = []

    async def cog_check(self, ctx):
        """Check to be sure that user know what he doing."""
        if ctx.author.id in self.aware_of_shit:
            return True
        await ctx.send(
            chat.warning(
                _(
                    "This command may abuse Discord API and therefore, "
                    "ban you or bot's owner, are you sure that you want to proceed?"
                )
            )
        )
        p = MessagePredicate.yes_or_no()
        await ctx.bot.wait_for("message", check=p)
        if p.result:
            self.aware_of_shit.append(ctx.author.id)
        return p.result

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    @checks.admin_or_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def massnick(self, ctx, *, nickname: str):
        """Mass nicknames everyone on the server"""
        server = ctx.guild
        counter = 0
        async with ctx.typing():
            for user in server.members:
                try:
                    await user.edit(
                        nick=nickname, reason=get_audit_reason(ctx.author, _("Massnick")),
                    )
                    await sleep(1)
                except discord.HTTPException:
                    counter += 1
                    continue
        await ctx.send(
            _("Finished nicknaming server. {} nicknames could not be completed.").format(counter)
        )

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    @checks.admin_or_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def resetnicks(self, ctx):
        """Resets nicknames on the server"""
        server = ctx.guild
        counter = 0
        async with ctx.typing():
            for user in server.members:
                try:
                    await user.edit(
                        nick=None, reason=get_audit_reason(ctx.author, _("Reset nicks"))
                    )
                    await sleep(1)
                except discord.HTTPException:
                    counter += 1
                    continue
        await ctx.send(
            _("Finished resetting server nicknames. Unable to reset {} nicknames.").format(counter)
        )

    @commands.command(aliases=["copyemojis"])
    @commands.guild_only()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    @checks.admin_or_permissions(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def massstealemoji(
        self, ctx: commands.Context, *emoji: Union[discord.Emoji, discord.PartialEmoji]
    ):
        """Steal all emoji provided in arguments"""
        nonanimated = list(filter(lambda e: not e.animated, emoji))
        animated = list(filter(lambda e: e.animated, emoji))
        nonanimated_available = ctx.guild.emoji_limit - len(
            [e for e in ctx.guild.emojis if not e.animated]
        )
        animated_available = ctx.guild.emoji_limit - len(
            [e for e in ctx.guild.emojis if e.animated]
        )
        if len(nonanimated) > nonanimated_available:
            await ctx.send(
                chat.error(
                    _(
                        "You tried to add too many emojis, you can add only {} emojis more to this server\n"
                        "You tried to add {}."
                    ).format(nonanimated_available, len(nonanimated))
                )
            )
            return
        if len(animated) > animated_available:
            await ctx.send(
                chat.error(
                    _(
                        "You tried to add too many animated emojis, you can add only {} emojis more to this server.\n"
                        "You tried to add {}."
                    ).format(animated_available, len(animated))
                )
            )
            return
        status = Counter()
        async with ctx.typing():
            for e in emoji:
                try:
                    await ctx.guild.create_custom_emoji(
                        name=e.name,
                        image=await e.url.read(),
                        reason=get_audit_reason(ctx.author, _("Emoji steal")),
                    )
                    await sleep(1)
                except discord.Forbidden:
                    status["Missing Permissions"] += 1
                except discord.HTTPException as e:
                    status[e.text] += 1
                else:
                    status["Success"] += 1
        await ctx.send(
            chat.info(
                _("Stealed emojis:\n{}").format(
                    chat.box(tabulate(status.most_common(), tablefmt="psql"), "ml")
                )
            )
        )
