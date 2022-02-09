import re
from asyncio import TimeoutError as AsyncTimeoutError
from random import choice
from typing import Optional, Union

import aiohttp
import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.mod import get_audit_reason
from redbot.core.utils.predicates import MessagePredicate

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json

_ = Translator("AdminUtils", __file__)

EMOJI_RE = re.compile(r"(<(a)?:[a-zA-Z0-9_]+:([0-9]+)>)")


@cog_i18n(_)
class AdminUtils(commands.Cog):
    """Useful commands for server administrators."""

    __version__ = "2.5.11"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(json_serialize=json.dumps)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    def format_help_for_context(self, ctx: commands.Context) -> str:  # Thanks Sinbad!
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\n**Version**: {self.__version__}"

    async def red_delete_data_for_user(self, **kwargs):
        return

    @staticmethod
    def check_channel_permission(
        ctx: commands.Context,
        channel_or_category: Union[discord.TextChannel, discord.CategoryChannel],
    ) -> bool:
        """
        Check user's permission in a channel, to be sure he can edit it.
        """
        mc = channel_or_category.permissions_for(ctx.author).manage_channels
        if mc:
            return True
        reason = (
            _("You are not allowed to edit this channel.")
            if not isinstance(channel_or_category, discord.CategoryChannel)
            else _("You are not allowed to edit in this category.")
        )
        raise commands.UserFeedbackCheckFailure(reason)

    @commands.command(name="prune")
    @commands.guild_only()
    @commands.admin_or_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def cleanup_users(self, ctx, days: Optional[int] = 1, *roles: discord.Role):
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
        pred = MessagePredicate.yes_or_no(ctx)
        if not ctx.assume_yes:
            roles_text = _("\nIncluding members in roles: {}\n").format(
                ", ".join(r.mention for r in roles)
            )
            await ctx.send(
                chat.warning(
                    _(
                        "You are about to kick **{to_kick}** inactive for **{days}** days members from this server. "
                        '{roles}Are you sure?\nTo agree, type "yes"'
                    ).format(to_kick=to_kick, days=days, roles=roles_text if roles else "")
                )
            )
            try:
                await self.bot.wait_for("message", check=pred, timeout=30)
            except AsyncTimeoutError:
                pass
        if ctx.assume_yes or pred.result:
            cleanup = await ctx.guild.prune_members(
                days=days, reason=get_audit_reason(ctx.author), roles=roles or None
            )
            await ctx.send(
                chat.info(
                    _(
                        "**{removed}**/**{all}** inactive members removed.\n"
                        "(They were inactive for **{days}** days)"
                    ).format(removed=cleanup, all=to_kick, days=days)
                )
            )
        else:
            await ctx.send(chat.error(_("Inactive members cleanup canceled.")))

    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_guild=True)
    async def restartvoice(self, ctx: commands.Context):
        """Change server's voice region to random and back

        Useful to reinitate all voice connections"""
        current_region = ctx.guild.region
        random_region = choice(
            [
                r
                for r in discord.VoiceRegion
                if not r.value.startswith("vip") and current_region != r
            ]
        )
        await ctx.guild.edit(region=random_region)
        await ctx.guild.edit(
            region=current_region,
            reason=get_audit_reason(ctx.author, _("Voice restart")),
        )
        await ctx.tick()

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.guild)
    @commands.admin_or_permissions(move_members=True)
    @commands.bot_has_guild_permissions(move_members=True)
    async def massmove(
        self,
        ctx: commands.Context,
        from_channel: discord.VoiceChannel,
        to_channel: discord.VoiceChannel = None,
    ):
        """Move all members from one voice channel to another

        Use double quotes if channel name has spaces"""
        fails = 0
        if not from_channel.members:
            await ctx.send(
                chat.error(_("There is no users in channel {}.").format(from_channel.mention))
            )
            return
        if not from_channel.permissions_for(ctx.me).move_members:
            await ctx.send(chat.error(_("I cant move users from that channel")))
            return
        if to_channel and not to_channel.permissions_for(ctx.me).connect:
            await ctx.send(chat.error(_("I cant move users to that channel")))
            return
        async with ctx.typing():
            for member in from_channel.members:
                try:
                    await member.move_to(
                        to_channel, reason=get_audit_reason(ctx.author, _("Massmove"))
                    )
                except discord.HTTPException:
                    fails += 1
                    continue
        await ctx.send(_("Finished moving users. {} members could not be moved.").format(fails))

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    async def emoji(self, ctx: commands.Context):
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
            await ctx.send(chat.error(_("Unable to get emoji from provided url: {}").format(e)))
            return
        try:
            await ctx.guild.create_custom_emoji(
                name=name,
                image=data,
                roles=roles,
                reason=get_audit_reason(
                    ctx.author,
                    _("Restricted to roles: {}").format(", ".join(role.name for role in roles))
                    if roles
                    else None,
                ),
            )
        except discord.InvalidArgument:
            await ctx.send(chat.error(_("This image type is unsupported, or link is incorrect")))
        except discord.HTTPException as e:
            await ctx.send(chat.error(_("An error occured on adding an emoji: {}").format(e)))
        else:
            await ctx.tick()

    @emoji.command(name="message", aliases=["steal"])
    async def emote_steal(
        self, ctx: commands.Context, name: str, message_id: discord.Message, *roles: discord.Role
    ):
        """
        Add an emoji from a specified message
        Use double quotes if role name has spaces

        Examples:
            `[p]emoji message Example 162379234070467641`
            `[p]emoji message RoleBased 162379234070467641 EmojiRole`
        """
        # TrustyJaid NotSoBot converter
        # https://github.com/TrustyJAID/Trusty-cogs/blob/a3e931bc6227645007b37c3f4f524c9fc9859686/notsobot/converter.py#L30-L36
        emoji = EMOJI_RE.search(message_id.content)
        if not emoji:
            await ctx.send(chat.error(_("No emojis found specified message.")))
            return
        url = (
            "https://cdn.discordapp.com/emojis/"
            f"{emoji.group(3)}.{'gif' if emoji.group(2) else 'png'}?v=1"
        )
        async with self.session.get(url) as r:
            data = await r.read()
        try:
            await ctx.guild.create_custom_emoji(
                name=name,
                image=data,
                roles=roles,
                reason=get_audit_reason(
                    ctx.author,
                    _("Restricted to roles: {}").format(", ".join(role.name for role in roles))
                    if roles
                    else None,
                ),
            )
            await ctx.tick()
        except discord.InvalidArgument:
            await ctx.send(
                _(
                    "This image type is not supported anymore or Discord returned incorrect data. Try again later."
                )
            )
            return
        except discord.HTTPException as e:
            await ctx.send(chat.error(_("An error occurred on adding an emoji: {}").format(e)))

    @emoji.command(name="rename")
    async def emoji_rename(
        self, ctx: commands.Context, emoji: discord.Emoji, name: str, *roles: discord.Role
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
        try:
            await emoji.edit(
                name=name,
                roles=roles,
                reason=get_audit_reason(
                    ctx.author,
                    _("Restricted to roles: ").format(", ".join(role.name for role in roles))
                    if roles
                    else None,
                ),
            )
        except discord.Forbidden:
            await ctx.send(chat.error(_("I can't edit this emoji")))
        await ctx.tick()

    @emoji.command(name="remove")
    async def emoji_remove(self, ctx: commands.Context, *, emoji: discord.Emoji):
        """Remove emoji from server"""
        if emoji.guild != ctx.guild:
            await ctx.send_help()
            return
        await emoji.delete(reason=get_audit_reason(ctx.author))
        await ctx.tick()

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def channel(self, ctx: commands.Context):
        """Manage channels"""
        pass

    @channel.group(name="create", aliases=["add"])
    async def channel_create(
        self,
        ctx: commands.Context,
    ):
        """Create a channel"""

    @channel_create.command(name="text")
    async def channel_create_text(
        self,
        ctx: commands.Context,
        category: Optional[discord.CategoryChannel] = None,
        *,
        name: str,
    ):
        """Create a text channel

        You can create the channel under a category if passed, else it is created under no category
        Use double quotes if category has spaces

        Examples:
            `[p]channel add text "The Zoo" awesome-channel` will create under the "The Zoo" category.
            `[p]channel add text awesome-channel` will create under no category, at the top.
        """
        if category:
            self.check_channel_permission(ctx, category)
        try:
            await ctx.guild.create_text_channel(
                name, category=category, reason=get_audit_reason(ctx.author)
            )
        except discord.Forbidden:
            await ctx.send(chat.error(_("I can't create channel in this category")))
        except discord.HTTPException as e:
            await ctx.send(chat.error(_("I am unable to create a channel: {}").format(e)))
        else:
            await ctx.tick()

    @channel_create.command(name="voice")
    async def channel_create_voice(
        self,
        ctx: commands.Context,
        category: Optional[discord.CategoryChannel] = None,
        *,
        name: str,
    ):
        """Create a voice channel

        You can create the channel under a category if passed, else it is created under no category
        Use double quotes if category has spaces

        Examples:
            `[p]channel add voice "The Zoo" Awesome Channel` will create under the "The Zoo" category.
            `[p]channel add voice Awesome Channel` will create under no category, at the top.
        """
        if category:
            self.check_channel_permission(ctx, category)
        try:
            await ctx.guild.create_voice_channel(
                name, category=category, reason=get_audit_reason(ctx.author)
            )
        except discord.Forbidden:
            await ctx.send(chat.error(_("I can't create channel in this category")))
        except discord.HTTPException as e:
            await ctx.send(chat.error(_("I am unable to create a channel: {}").format(e)))
        else:
            await ctx.tick()

    @channel.command(name="rename")
    async def channel_rename(
        self,
        ctx: commands.Context,
        channel: Union[discord.TextChannel, discord.VoiceChannel],
        *,
        name: str,
    ):
        """Rename a channel

        Use double quotes if channel has spaces

        Examples:
            `[p]channel rename channel new-channel-name`
        """
        self.check_channel_permission(ctx, channel)
        try:
            await channel.edit(name=name, reason=get_audit_reason(ctx.author))
        except discord.Forbidden:
            await ctx.send(chat.error(_("I can't rename this channel")))
        except discord.HTTPException as e:
            await ctx.send(chat.error(_("I am unable to rename this channel: {}").format(e)))
        else:
            await ctx.tick()

    @channel.command(name="delete", aliases=["remove"])
    async def channel_delete(
        self, ctx: commands.Context, *, channel: Union[discord.TextChannel, discord.VoiceChannel]
    ):
        """Remove a channel from server

        Example:
            `[p]channel delete channel`
        """
        self.check_channel_permission(ctx, channel)
        pred = MessagePredicate.yes_or_no(ctx)
        if not ctx.assume_yes:
            await ctx.send(
                chat.warning(
                    _(
                        "You are about to delete channel {channel}. This cannot be undone. Are you sure?\n"
                        'To agree, type "yes"'
                    ).format(channel=channel.mention)
                )
            )
            try:
                await self.bot.wait_for("message", check=pred, timeout=30)
            except AsyncTimeoutError:
                pass
        if ctx.assume_yes or pred.result:
            try:
                await channel.delete(reason=get_audit_reason(ctx.author))
            except discord.Forbidden:
                await ctx.send(chat.error(_("I can't delete this channel")))
            except discord.HTTPException as e:
                await ctx.send(chat.error(_("I am unable to delete a channel: {}").format(e)))
            else:
                await ctx.tick()
