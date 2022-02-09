import logging
from datetime import datetime, timezone
from pprint import pformat
from typing import Union

import discord
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu


def is_channel_set(channel_type: str):
    """Checks if server has set channel for logging"""

    async def predicate(ctx):
        if ctx.guild:
            return ctx.guild.get_channel(
                await getattr(ctx.cog.config.guild(ctx.guild), f"{channel_type}_channel")()
            )

    return commands.check(predicate)


async def ignore_config_add(config: list, item):
    """Adds item to provided config list"""
    if item.id in config:
        config.remove(item.id)
    else:
        config.append(item.id)


log = logging.getLogger("red.fixator10-cogs.messageslog")
_ = Translator("MessagesLog", __file__)


@cog_i18n(_)
class MessagesLog(commands.Cog):
    """Log deleted and edited messages to the defined channel"""

    __version__ = "2.3.13"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xB0FCB74A18A548D084B6312E018AC474)
        default_guild = {
            "delete_channel": None,
            "edit_channel": None,
            "bulk_delete_channel": None,
            "deletion": True,
            "editing": True,
            "save_bulk": False,
            "ignored_channels": [],
            "ignored_users": [],
            "ignored_categories": [],
        }
        self.config.register_guild(**default_guild)

    async def initialize(self):  # sourcery skip: last-if-guard
        """Update configs

        Versions:
        1. Copy channel to channel types"""
        if not await self.config.config_version() or await self.config.config_version() < 1:
            log.info("Updating config from version 1 to version 2")
            for guild, data in (await self.config.all_guilds()).items():
                if data["channel"]:
                    log.info(f"Updating config for guild {guild}")
                    guild_config = self.config.guild_from_id(guild)
                    await guild_config.delete_channel.set(data["channel"])
                    await guild_config.edit_channel.set(data["channel"])
                    await guild_config.bulk_delete_channel.set(data["channel"])
                    await guild_config.channel.clear()
            log.info("Config updated to version 1")
            await self.config.config_version.set(1)

    def format_help_for_context(self, ctx: commands.Context) -> str:  # Thanks Sinbad!
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\n**Version**: {self.__version__}"

    async def red_delete_data_for_user(self, **kwargs):
        return

    @commands.group(autohelp=True, aliases=["messagelog", "messageslogs", "messagelogs"])
    @commands.admin_or_permissions(manage_guild=True)
    async def messageslog(self, ctx):
        """Manage message logging"""
        pass

    @messageslog.group(name="channel")
    async def set_channel(self, ctx):
        """Set the channels for logs"""
        pass

    @set_channel.command(name="delete")
    async def delete_channel(self, ctx, *, channel: discord.TextChannel = None):
        """Set the channel for deleted messages logs

        If channel is not specified, then logging will be disabled"""
        await self.config.guild(ctx.guild).delete_channel.set(channel.id if channel else None)
        await ctx.tick()

    @set_channel.command(name="edit")
    async def edit_channel(self, ctx, *, channel: discord.TextChannel = None):
        """Set the channel for edited messages logs

        If channel is not specified, then logging will be disabled"""
        await self.config.guild(ctx.guild).edit_channel.set(channel.id if channel else None)
        await ctx.tick()

    @set_channel.command(name="bulk")
    async def bulk_channel(self, ctx, *, channel: discord.TextChannel = None):
        """Set the channel for bulk deletion logs

        If channel is not specified, then logging will be disabled"""
        await self.config.guild(ctx.guild).bulk_delete_channel.set(channel.id if channel else None)
        await ctx.tick()

    @set_channel.command(name="all")
    async def all_channel(self, ctx, *, channel: discord.TextChannel = None):
        """Set the channel for all logs

        If channel is not specified, then logging will be disabled"""
        await self.config.guild(ctx.guild).delete_channel.set(channel.id if channel else None)
        await self.config.guild(ctx.guild).edit_channel.set(channel.id if channel else None)
        await self.config.guild(ctx.guild).bulk_delete_channel.set(channel.id if channel else None)
        await ctx.tick()

    @set_channel.command(name="settings")
    async def channel_settings(self, ctx):
        """View current channels settings"""
        settings = []
        if delete := await self.config.guild(ctx.guild).delete_channel():
            settings.append(_("Deletion: {}").format(ctx.guild.get_channel(delete)))
        if edit := await self.config.guild(ctx.guild).edit_channel():
            settings.append(_("Edit: {}").format(ctx.guild.get_channel(edit)))
        if bulk := await self.config.guild(ctx.guild).bulk_delete_channel():
            settings.append(_("Bulk deletion: {}").format(ctx.guild.get_channel(bulk)))
        await ctx.send("\n".join(settings) or chat.info(_("No channels set")))

    @messageslog.group()
    async def toggle(self, ctx):
        """Toggle logging"""
        pass

    @toggle.command(name="delete")
    @is_channel_set("delete")
    async def mess_delete(self, ctx):
        """Toggle logging of message deletion"""
        deletion = self.config.guild(ctx.guild).deletion
        await deletion.set(not await deletion())
        state = _("enabled") if await self.config.guild(ctx.guild).deletion() else _("disabled")
        await ctx.send(chat.info(_("Message deletion logging {}").format(state)))

    @toggle.command(name="edit")
    @is_channel_set("edit")
    async def mess_edit(self, ctx):
        """Toggle logging of message editing"""
        editing = self.config.guild(ctx.guild).editing
        await editing.set(not await editing())
        state = _("enabled") if await self.config.guild(ctx.guild).editing() else _("disabled")
        await ctx.send(chat.info(_("Message editing logging {}").format(state)))

    @toggle.command(name="bulk", alias=["savebulk"])
    @is_channel_set("bulk_delete")
    async def mess_bulk(self, ctx):
        """Toggle saving of bulk message deletion"""
        save_bulk = self.config.guild(ctx.guild).save_bulk
        await save_bulk.set(not await save_bulk())
        state = _("enabled") if await self.config.guild(ctx.guild).save_bulk() else _("disabled")
        await ctx.send(chat.info(_("Bulk message removal saving {}").format(state)))

    @messageslog.command()
    async def ignore(
        self,
        ctx,
        *ignore: Union[discord.Member, discord.TextChannel, discord.CategoryChannel],
    ):
        """Manage message logging blocklist

        Shows blocklist if no arguments provided
        You can ignore text channels, categories and members
        If item is in blocklist, removes it"""
        if not ignore:
            users = await self.config.guild(ctx.guild).ignored_users()
            channels = await self.config.guild(ctx.guild).ignored_channels()
            categories = await self.config.guild(ctx.guild).ignored_categories()
            users = [ctx.guild.get_member(m).mention for m in users if ctx.guild.get_member(m)]
            channels = [
                ctx.guild.get_channel(m).mention for m in channels if ctx.guild.get_channel(m)
            ]
            categories = [
                ctx.guild.get_channel(m).mention for m in categories if ctx.guild.get_channel(m)
            ]
            if not any([users, channels, categories]):
                await ctx.send(chat.info(_("Nothing is ignored")))
                return
            users_pages = [
                discord.Embed(title=_("Ignored users"), description=page)
                for page in chat.pagify("\n".join(users), page_length=2048)
            ]

            channels_pages = [
                discord.Embed(title=_("Ignored channels"), description=page)
                for page in chat.pagify("\n".join(channels), page_length=2048)
            ]

            categories_pages = [
                discord.Embed(title=_("Ignored categories"), description=page)
                for page in chat.pagify("\n".join(categories), page_length=2048)
            ]

            pages = users_pages + channels_pages + categories_pages
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            guild = self.config.guild(ctx.guild)
            for item in ignore:
                if isinstance(item, discord.Member):
                    async with guild.ignored_users() as ignored_users:
                        await ignore_config_add(ignored_users, item)
                elif isinstance(item, discord.TextChannel):
                    async with guild.ignored_channels() as ignored_channels:
                        await ignore_config_add(ignored_channels, item)
                elif isinstance(item, discord.CategoryChannel):
                    async with guild.ignored_categories() as ignored_categories:
                        await ignore_config_add(ignored_categories, item)
            await ctx.tick()

    @commands.Cog.listener("on_message_delete")
    async def message_deleted(self, message: discord.Message):
        if not message.guild:
            return
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        logchannel = message.guild.get_channel(
            await self.config.guild(message.guild).delete_channel()
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
                (await self.bot.get_context(message)).command,
                message.channel.id in await self.config.guild(message.guild).ignored_channels(),
                message.author.id in await self.config.guild(message.guild).ignored_users(),
                message.author.bot,
                message.channel.nsfw and not logchannel.nsfw,
            ]
        ):
            return
        await set_contextual_locales_from_guild(self.bot, message.guild)
        embed = discord.Embed(
            title=_("Message deleted"),
            description=message.system_content or chat.inline(_("No text")),
            timestamp=message.created_at,
            color=message.author.color,
        )
        if message.attachments:
            embed.add_field(
                name=_("Attachments"),
                value="\n".join(
                    _("[{0.filename}]({0.url}) ([Cached]({0.proxy_url}))").format(a)
                    for a in message.attachments
                ),
            )
        embed.set_author(name=message.author, icon_url=message.author.avatar_url)
        embed.set_footer(text=_("ID: {} • Sent at").format(message.id))
        embed.add_field(name=_("Channel"), value=message.channel.mention)
        try:
            await logchannel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener("on_raw_message_delete")
    async def raw_message_deleted(self, payload: discord.RawMessageDeleteEvent):
        if payload.cached_message:
            return
        if not payload.guild_id:
            return
        if await self.bot.cog_disabled_in_guild_raw(self.qualified_name, payload.guild_id):
            return
        guild = self.bot.get_guild(payload.guild_id)
        channel = self.bot.get_channel(payload.channel_id)
        logchannel = guild.get_channel(await self.config.guild(guild).delete_channel())
        if not logchannel:
            return
        if (
            channel.category
            and channel.category.id in await self.config.guild(guild).ignored_categories()
        ):
            return
        if any(
            [
                not await self.config.guild(guild).deletion(),
                channel.id in await self.config.guild(guild).ignored_channels(),
                channel.nsfw and not logchannel.nsfw,
            ]
        ):
            return
        await set_contextual_locales_from_guild(self.bot, guild)
        embed = discord.Embed(
            title=_("Old message deleted"),
            timestamp=discord.utils.snowflake_time(payload.message_id),
            color=await self.bot.get_embed_colour(channel),
        )
        embed.set_footer(text=_("ID: {} • Sent at").format(payload.message_id))
        embed.add_field(name=_("Channel"), value=channel.mention)
        try:
            await logchannel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener("on_raw_bulk_message_delete")
    async def raw_bulk_message_deleted(self, payload: discord.RawBulkMessageDeleteEvent):
        # sourcery skip: comprehension-to-generator
        if not payload.guild_id:
            return
        if await self.bot.cog_disabled_in_guild_raw(self.qualified_name, payload.guild_id):
            return
        guild = self.bot.get_guild(payload.guild_id)
        channel = self.bot.get_channel(payload.channel_id)
        logchannel = guild.get_channel(await self.config.guild(guild).bulk_delete_channel())
        if not logchannel:
            return
        if (
            channel.category
            and channel.category.id in await self.config.guild(guild).ignored_categories()
        ):
            return
        if any(
            [
                not await self.config.guild(guild).deletion(),
                channel.id in await self.config.guild(guild).ignored_channels(),
                channel.nsfw and not logchannel.nsfw,
            ]
        ):
            return
        await set_contextual_locales_from_guild(self.bot, guild)
        save_bulk = await self.config.guild(guild).save_bulk()
        messages_dump = None
        if payload.cached_messages and save_bulk:
            n = "\n"
            messages_dump = chat.text_to_file(
                "\n\n".join(
                    [
                        f"[{m.id}]\n"
                        f"[Author]:     {m.author}\n"
                        f"[Channel]:    {m.channel.name} ({m.channel.id})\n"
                        f"[Created at]: {m.created_at}\n"
                        f"[Content]:\n"
                        f"{m.system_content}\n"
                        f"[Embeds]:\n"
                        f"{n.join([pformat(e.to_dict()) for e in m.embeds])}"
                        async for m in AsyncIter(payload.cached_messages)
                        if m.guild.id == guild.id
                    ]
                ),
                filename=f"{guild.id}.txt",
            )
        embed = discord.Embed(
            title=_("Multiple messages deleted"),
            description=_("{} messages removed").format(len(payload.message_ids))
            + (
                "\n" + _("{} messages saved to file above").format(len(payload.cached_messages))
                if payload.cached_messages and save_bulk
                else ""
            ),
            timestamp=datetime.now(timezone.utc),
            color=await self.bot.get_embed_colour(channel),
        )
        embed.add_field(name=_("Channel"), value=channel.mention)
        try:
            await logchannel.send(embed=embed, file=messages_dump)
        except discord.Forbidden:
            pass

    @commands.Cog.listener("on_message_edit")
    async def message_edited(self, before: discord.Message, after: discord.Message):
        if not before.guild:
            return
        if await self.bot.cog_disabled_in_guild(self, before.guild):
            return
        logchannel = before.guild.get_channel(await self.config.guild(before.guild).edit_channel())
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
                not await self.config.guild(before.guild).editing(),
                (await self.bot.get_context(before)).command,
                before.channel.id in await self.config.guild(before.guild).ignored_channels(),
                before.author.id in await self.config.guild(before.guild).ignored_users(),
                before.content == after.content,
                before.author.bot,
                before.channel.nsfw and not logchannel.nsfw,
            ]
        ):
            return
        await set_contextual_locales_from_guild(self.bot, before.guild)
        embed = discord.Embed(
            title=_("Message edited"),
            description=before.content or chat.inline(_("No text")),
            timestamp=before.created_at,
            color=before.author.color,
        )
        embed.add_field(name=_("Now"), value=_("[View message]({})").format(after.jump_url))
        if before.attachments:
            embed.add_field(
                name=_("Attachments"),
                value="\n".join(
                    _("[{0.filename}]({0.url}) ([Cached]({0.proxy_url}))").format(a)
                    for a in before.attachments
                ),
            )
        embed.set_author(name=before.author, icon_url=before.author.avatar_url)
        embed.set_footer(text=_("ID: {} • Sent at").format(before.id))
        try:
            await logchannel.send(embed=embed)
        except discord.Forbidden:
            pass
