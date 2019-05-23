from typing import Union

import discord
from redbot.core import checks
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


async def is_channel_set(ctx: commands.Context):
    """Checks if server has set channel for logging"""
    return ctx.guild.get_channel(await ctx.cog.config.guild(ctx.guild).channel())


_ = Translator("MessagesLog", __file__)


@cog_i18n(_)
class MessagesLog(commands.Cog):
    """Log deleted and redacted messages to the defined channel"""

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=0xB0FCB74A18A548D084B6312E018AC474
        )
        default_guild = {
            "channel": None,
            "deletion": True,
            "editing": True,
            "ignored_channels": [],
            "ignored_users": [],
            "ignored_categories": [],
        }
        self.config.register_guild(**default_guild)

    @commands.group(
        autohelp=True, aliases=["messagelog", "messageslogs", "messagelogs"]
    )
    @checks.admin_or_permissions(manage_guild=True)
    async def messageslog(self, ctx):
        """Manage message logging"""
        pass

    @messageslog.command()
    async def channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel for logs

        If channel is not provided, then logging will be disabled"""
        await self.config.guild(ctx.guild).channel.set(channel.id if channel else None)
        await ctx.tick()

    @messageslog.command(name="delete")
    @commands.check(is_channel_set)
    async def mess_delete(self, ctx):
        """Toggle logging of message deletion"""
        deletion = self.config.guild(ctx.guild).deletion
        await deletion.set(not await deletion())
        state = (
            _("enabled")
            if await self.config.guild(ctx.guild).deletion()
            else _("disabled")
        )
        await ctx.send(chat.info(_("Message deletion logging {}").format(state)))

    @messageslog.command(name="edit")
    @commands.check(is_channel_set)
    async def mess_edit(self, ctx):
        """Toggle logging of message editing"""
        editing = self.config.guild(ctx.guild).editing
        await editing.set(not await editing())
        state = (
            _("enabled")
            if await self.config.guild(ctx.guild).editing()
            else _("disabled")
        )
        await ctx.send(chat.info(_("Message editing logging {}").format(state)))

    @messageslog.command()
    @commands.check(is_channel_set)
    async def ignore(
            self,
            ctx,
            *ignore: Union[discord.Member, discord.TextChannel, discord.CategoryChannel],
    ):
        """Manage message logging blacklist

        Shows blacklist if no arguments provided
        You can ignore text channels, categories and members
        If item is in blacklist, removes it"""
        if not ignore:
            users = await self.config.guild(ctx.guild).ignored_users()
            channels = await self.config.guild(ctx.guild).ignored_channels()
            categories = await self.config.guild(ctx.guild).ignored_categories()
            users = [
                ctx.guild.get_member(m).mention
                for m in users
                if ctx.guild.get_member(m)
            ]
            channels = [
                ctx.guild.get_channel(m).mention
                for m in channels
                if ctx.guild.get_channel(m)
            ]
            categories = [
                ctx.guild.get_channel(m).mention
                for m in categories
                if ctx.guild.get_channel(m)
            ]
            if not any([users, channels, categories]):
                await ctx.send(chat.info(_("Nothing is ignored")))
                return
            users_pages = []
            channels_pages = []
            categories_pages = []
            for page in chat.pagify("\n".join(users), page_length=2048):
                users_pages.append(
                    discord.Embed(title=_("Ignored users"), description=page)
                )
            for page in chat.pagify("\n".join(channels), page_length=2048):
                channels_pages.append(
                    discord.Embed(title=_("Ignored channels"), description=page)
                )
            for page in chat.pagify("\n".join(categories), page_length=2048):
                categories_pages.append(
                    discord.Embed(title=_("Ignored categories"), description=page)
                )
            pages = users_pages + channels_pages + categories_pages
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            guild = self.config.guild(ctx.guild)
            for item in ignore:
                if isinstance(item, discord.Member):
                    async with guild.ignored_users() as ignored_users:
                        await self.ignore_config_add(ignored_users, item)
                elif isinstance(item, discord.TextChannel):
                    async with guild.ignored_channels() as ignored_channels:
                        await self.ignore_config_add(ignored_channels, item)
                elif isinstance(item, discord.CategoryChannel):
                    async with guild.ignored_categories() as ignored_categories:
                        await self.ignore_config_add(ignored_categories, item)
            await ctx.tick()

    @ignore.error
    async def ignore_error(self, ctx, error):
        if isinstance(error, commands.BadUnionArgument):
            await ctx.send_help()

    async def ignore_config_add(self, config: list, item):
        """Adds item to provided config list"""
        if item.id in config:
            config.remove(item.id)
        else:
            config.append(item.id)

    @commands.Cog.listener("on_message_delete")
    async def message_deleted(self, message: discord.Message):
        if not message.guild:
            return
        logchannel = message.guild.get_channel(
            await self.config.guild(message.guild).channel()
        )
        if not logchannel:
            return
        if (
                message.channel.category
                and message.channel.category.id
                in await self.config.guild(message.guild).ignored_categories()
        ):
            return
        if any(
            [
                not await self.config.guild(message.guild).deletion(),
                not message.guild.get_channel(
                    await self.config.guild(message.guild).channel()
                ),
                any(
                    message.content.startswith(prefix)
                    for prefix in await self.bot.get_prefix(message)
                ),
                message.channel.id
                in await self.config.guild(message.guild).ignored_channels(),
                message.author.id
                in await self.config.guild(message.guild).ignored_users(),
                not message.content,
                message.author.bot,
                message.channel.nsfw and not logchannel.nsfw,
            ]
        ):
            return
        embed = discord.Embed(
            title=_("Message deleted"),
            description=message.content,
            timestamp=message.created_at,
            color=message.author.color,
        )
        if message.attachments:
            embed.add_field(
                name=_("Attachments"),
                value="\n".join(
                    [f"[{a.filename}]({a.url})" for a in message.attachments]
                ),
            )
        embed.set_author(name=message.author, icon_url=message.author.avatar_url)
        embed.set_footer(text=_("ID: {} • Sent at").format(message.id))
        embed.add_field(name=_("Channel"), value=message.channel.mention)
        try:
            await logchannel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener("on_message_edit")
    async def message_redacted(self, before: discord.Message, after: discord.Message):
        if not before.guild:
            return
        logchannel = before.guild.get_channel(
            await self.config.guild(before.guild).channel()
        )
        if not logchannel:
            return
        if (
                before.channel.category
                and before.channel.category.id
                in await self.config.guild(before.guild).ignored_categories()
        ):
            return
        if any(
            [
                not await self.config.guild(before.guild).deletion(),
                not before.guild.get_channel(
                    await self.config.guild(before.guild).channel()
                ),
                any(
                    before.content.startswith(prefix)
                    for prefix in await self.bot.get_prefix(before)
                ),
                before.channel.id
                in await self.config.guild(before.guild).ignored_channels(),
                before.author.id
                in await self.config.guild(before.guild).ignored_users(),
                not after.content,
                before.content == after.content,
                before.author.bot,
                before.channel.nsfw and not logchannel.nsfw,
            ]
        ):
            return
        embed = discord.Embed(
            title=_("Message redacted (Before)"),
            description=before.content,
            timestamp=before.created_at,
            color=before.author.color,
        )
        embed.add_field(
            name=_("Now"), value=_("[View message]({})").format(after.jump_url)
        )
        if before.attachments:
            embed.add_field(
                name=_("Attachments"),
                value="\n".join(
                    [f"[{a.filename}]({a.url})" for a in before.attachments]
                ),
            )
        embed.set_author(name=before.author, icon_url=before.author.avatar_url)
        embed.set_footer(text=_("ID: {} • Sent at").format(before.id))
        try:
            await logchannel.send(embed=embed)
        except discord.Forbidden:
            pass
