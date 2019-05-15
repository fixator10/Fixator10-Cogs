from asyncio import TimeoutError as AsyncTimeoutError
from asyncio import sleep

import aiohttp
import discord
from redbot.core import checks
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.mod import get_audit_reason
from redbot.core.utils.predicates import MessagePredicate

_ = Translator("AdminUtils", __file__)


@cog_i18n(_)
class AdminUtils(commands.Cog):
    # noinspection PyMissingConstructor
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.command(name="prune")
    @commands.guild_only()
    @checks.admin_or_permissions(kick_members=True)
    @checks.bot_has_permissions(kick_members=True)
    async def cleanup_users(self, ctx, days: int = 1):
        """Cleanup inactive server members"""
        if days > 30:
            await ctx.send(
                chat.info(
                    _(
                        "Due to Discord Restrictions, you cannot use more than 30 days for that cmd."
                    )
                )
            )
            days = 30
        elif days <= 0:
            await ctx.send(chat.info(_('"days" arg cannot be less than 1...')))
            days = 1
        to_kick = await ctx.guild.estimate_pruned_members(days=days)
        await ctx.send(
            chat.warning(
                _(
                    "You about to kick **{to_kick}** inactive for **{days}** days members from this server. "
                    'Are you sure?\nTo agree, type "yes"'
                ).format(to_kick=to_kick, days=days)
            )
        )
        pred = MessagePredicate.yes_or_no(ctx)
        try:
            await self.bot.wait_for("message", check=pred, timeout=30)
        except AsyncTimeoutError:
            pass
        if pred.result:
            cleanup = await ctx.guild.prune_members(
                days=days, reason=get_audit_reason(ctx.author)
            )
            await ctx.send(
                chat.info(
                    _(
                        "**{removed}**/**{all}** inactive members removed.\n"
                        "(They was inactive for **{days}** days)"
                    ).format(removed=cleanup, all=to_kick, days=days)
                )
            )
        else:
            await ctx.send(chat.error(_("Inactive members cleanup canceled.")))

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    @checks.admin_or_permissions(manage_nicknames=True)
    @checks.bot_has_permissions(manage_nicknames=True)
    async def massnick(self, ctx, *, nickname: str):
        """Mass nicknames everyone on the server"""
        server = ctx.guild
        counter = 0
        async with ctx.typing():
            for user in server.members:
                try:
                    await user.edit(
                        nick=nickname,
                        reason=get_audit_reason(ctx.author, _("Massnick")),
                    )
                    await sleep(1)
                except discord.HTTPException:
                    counter += 1
                    continue
        await ctx.send(
            _(
                "Finished nicknaming server. {} nicknames could not be completed."
            ).format(counter)
        )

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    @checks.admin_or_permissions(manage_nicknames=True)
    @checks.bot_has_permissions(manage_nicknames=True)
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
            _(
                "Finished resetting server nicknames. Unable to reset {} nicknames."
            ).format(counter)
        )

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_emojis=True)
    @checks.bot_has_permissions(manage_emojis=True)
    async def emoji(self, ctx):
        """Manage emoji"""
        pass

    @emoji.command(name="add")
    async def emoji_add(self, ctx, name: str, url: str, *roles: discord.Role):
        """Create custom emoji

        Use double quotes if role name has spaces

        Examples:
            `[p]emoji add Example https://example.com/image.png`
            `[p]emoji add RoleBased https://example.com/image.png EmojiRole "Test image"`
        """
        try:
            async with self.session.get(url) as r:
                data = await r.read()
        except Exception as e:
            await ctx.send(
                chat.error(_("Unable to get emoji from provided url: {}").format(e))
            )
            return
        try:
            await ctx.guild.create_custom_emoji(
                name=name,
                image=data,
                roles=roles,
                reason=get_audit_reason(
                    ctx.author,
                    _("Restricted to roles: {}").format(
                        ", ".join([f"{role.name}" for role in roles])
                    )
                    if roles
                    else None,
                ),
            )
        except discord.InvalidArgument:
            await ctx.send(
                chat.error(_("This image type is unsupported, or link is incorrect"))
            )
        except discord.HTTPException as e:
            await ctx.send(
                chat.error(_("An error occured on adding an emoji: {}").format(e))
            )
        else:
            await ctx.tick()

    @emoji.command(name="rename")
    async def emoji_rename(
        self, ctx, emoji: discord.Emoji, name: str, *roles: discord.Role
    ):
        """Rename emoji and restrict to certain roles
        Only this roles will be able to use this emoji

        Use double quotes if role name has spaces

        Examples:
            `[p]emoji rename emoji NewEmojiName`
            `[p]emoji rename emoji NewEmojiName Administrator "Allowed role"`
        """
        if emoji.guild != ctx.guild:
            await ctx.send_help()
            return
        await emoji.edit(
            name=name,
            roles=roles,
            reason=get_audit_reason(
                ctx.author,
                _("Restricted to roles: ").format(
                    ", ".join([f"{role.name}" for role in roles])
                )
                if roles
                else None,
            ),
        )
        await ctx.tick()

    @emoji.command(name="remove")
    async def emoji_remove(self, ctx, *, emoji: discord.Emoji):
        """Remove emoji from server"""
        if emoji.guild != ctx.guild:
            await ctx.send_help()
            return
        await emoji.delete(reason=get_audit_reason(ctx.author))
        await ctx.tick()
