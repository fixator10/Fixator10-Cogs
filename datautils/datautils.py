from asyncio import TimeoutError as AsyncTimeoutError
from textwrap import shorten
from types import SimpleNamespace
from typing import Optional, Union

import discord
import tabulate
from fixcogsutils.dpy_future import TimestampStyle, get_markdown_timestamp
from fixcogsutils.formatting import bool_emojify
from redbot.core import commands
from redbot.core.i18n import cog_i18n
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.predicates import ReactionPredicate

from .common_variables import CHANNEL_TYPE_EMOJIS, GUILD_FEATURES, KNOWN_CHANNEL_TYPES
from .embeds import emoji_embed
from .menus import ActivityPager, BaseMenu, ChannelsMenu, ChannelsPager, EmojiPager, PagePager
from .utils import _


@cog_i18n(_)
class DataUtils(commands.Cog):
    """Commands for getting information about users or servers."""

    __version__ = "2.6.8"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot

    async def red_delete_data_for_user(self, **kwargs):
        return

    @commands.command(aliases=["fetchuser"], hidden=True)
    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.bot_has_permissions(embed_links=True)
    async def getuserinfo(self, ctx, user_id: int):
        """Get info about any Discord's user by ID"""
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            await ctx.send(chat.error(_("Discord user with ID `{}` not found").format(user_id)))
            return
        except discord.HTTPException:
            await ctx.send(
                chat.warning(
                    _("I was unable to get data about user with ID `{}`. Try again later").format(
                        user_id
                    )
                )
            )
            return
        em = discord.Embed(
            title=chat.escape(str(user), formatting=True),
            timestamp=user.created_at,
            color=await ctx.embed_color(),
        )
        em.add_field(name=_("ID"), value=user.id)
        em.add_field(name=_("Bot?"), value=bool_emojify(user.bot))
        em.add_field(name=_("System?"), value=bool_emojify(user.system))
        em.add_field(name=_("Mention"), value=user.mention)
        em.add_field(
            name=_("Default avatar"),
            value=f"[{user.default_avatar}]({user.default_avatar_url})",
        )
        if user.avatar:
            em.add_field(
                name=_("Avatar"),
                value=f"[`{user.avatar}`]({user.avatar_url_as(static_format='png', size=4096)})",
            )
        if user.public_flags.value:
            em.add_field(
                name=_("Public flags"),
                value="\n".join(
                    str(flag)[10:].replace("_", " ").capitalize()
                    for flag in user.public_flags.all()
                ),
                inline=False,
            )
        em.set_image(url=user.avatar_url_as(static_format="png", size=4096))
        em.set_thumbnail(url=user.default_avatar_url)
        em.set_footer(text=_("Created at"))
        await ctx.send(embed=em)

    @commands.command(aliases=["widgetinfo"], hidden=True)
    @commands.bot_has_permissions(embed_links=True)
    async def fetchwidget(self, ctx, *, server_id: int):
        """Get data about server by ID via server's widget"""
        try:
            widget = await self.bot.fetch_widget(server_id)
        except discord.Forbidden:
            await ctx.send(chat.error(_("Widget is disabled for this server.")))
            return
        except discord.HTTPException as e:
            await ctx.send(chat.error(_("Widget for that server is not found: {}").format(e.text)))
            return
        try:
            invite = await widget.fetch_invite()
        except discord.HTTPException:
            invite = None
        em = discord.Embed(
            title=_("Server info"), color=await ctx.embed_color(), url=widget.json_url
        )
        em.add_field(name=_("Name"), value=chat.escape(widget.name, formatting=True))
        stats_text = _(
            "**Online member count:** {members}\n" "**Voice channel count:** {channels}"
        ).format(members=len(widget.members), channels=len(widget.channels))
        if invite:
            guild = invite.guild
            em.description = guild.description and guild.description or None
            stats_text += "\n" + _(
                "**Server ID**: {guild_id}\n"
                "**Approximate member count:** {approx_members}\n"
                "**Approx. active members count:** {approx_active}\n"
                "**Invite Channel:** {channel}"
            ).format(
                guild_id=guild.id,
                approx_members=invite.approximate_member_count,
                approx_active=invite.approximate_presence_count,
                channel=chat.escape(invite.channel.name, formatting=True),
            )
            if guild.features:
                em.add_field(
                    name=_("Features"),
                    value="\n".join(_(GUILD_FEATURES.get(f, f)) for f in guild.features).format(
                        banner=guild.banner and f" [🔗]({guild.banner_url_as(format='png')})" or "",
                        splash=guild.splash and f" [🔗]({guild.splash_url_as(format='png')})" or "",
                        discovery=getattr(guild, "discovery_splash", None)
                        and f" [🔗]({guild.discovery_splash_url_as(format='png')})"
                        or "",
                    ),
                    inline=False,
                )
            if invite.guild.icon:
                em.set_image(url=invite.guild.icon_url_as(static_format="png", size=4096))
        em.add_field(name=_("Stats"), value=stats_text, inline=False)
        if widget.invite_url:
            em.add_field(name=_("Widget's invite"), value=widget.invite_url)
        await ctx.send(embed=em)

    @commands.command(aliases=["memberinfo", "membinfo"])
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def uinfo(self, ctx, *, member: discord.Member = None):
        """Information on a user"""
        if member is None:
            member = ctx.message.author
        em = discord.Embed(
            title=chat.escape(str(member), formatting=True),
            color=member.color.value and member.color or discord.Embed.Empty,
        )
        if member.nick:
            em.add_field(name=_("Nickname"), value=member.nick)
        else:
            em.add_field(name=_("Name"), value=member.name)
        em.add_field(
            name=_("Client"),
            value="📱: {}\n"
            "🖥: {}\n"
            "🌎: {}".format(
                str(member.mobile_status).capitalize(),
                str(member.desktop_status).capitalize(),
                str(member.web_status).capitalize(),
            ),
        )
        em.add_field(
            name=_("Joined server"),
            value=get_markdown_timestamp(member.joined_at, TimestampStyle.datetime_long),
        )
        em.add_field(name="ID", value=member.id)
        em.add_field(
            name=_("Exists since"),
            value=get_markdown_timestamp(member.created_at, TimestampStyle.datetime_long),
        )
        if member.color.value:
            em.add_field(name=_("Color"), value=member.colour)
        if member.premium_since:
            em.add_field(
                name=_("Boosted server"),
                value=get_markdown_timestamp(member.premium_since, TimestampStyle.datetime_long),
            )
        em.add_field(name=_("Bot?"), value=bool_emojify(member.bot))
        em.add_field(name=_("System?"), value=bool_emojify(member.system))
        em.add_field(
            name=_("Server permissions"),
            value="[{0}](https://cogs.fixator10.ru/permissions-calculator/?v={0})".format(
                member.guild_permissions.value
            ),
        )
        if member.voice:
            em.add_field(name=_("In voice channel"), value=member.voice.channel.mention)
        em.add_field(
            name=_("Mention"),
            value=f"{member.mention}\n{chat.inline(member.mention)}",
            inline=False,
        )
        if roles := [role.name for role in member.roles if not role.is_default()]:
            em.add_field(
                name=_("Roles"),
                value=chat.escape("\n".join(roles), formatting=True),
                inline=False,
            )
        if member.public_flags.value:
            em.add_field(
                name=_("Public flags"),
                value="\n".join(
                    [
                        str(flag)[10:].replace("_", " ").capitalize()
                        for flag in member.public_flags.all()
                    ]
                ),
                inline=False,
            )
        em.set_image(url=member.avatar_url_as(static_format="png", size=4096))
        # em.set_thumbnail(url=member.default_avatar_url)
        await ctx.send(embed=em)

    @commands.command(aliases=["activity"])
    @commands.guild_only()
    @commands.mod_or_permissions(embed_links=True)
    async def activities(self, ctx, *, member: discord.Member = None):
        """List user's activities"""
        if member is None:
            member = ctx.message.author
        if not (activities := member.activities):
            await ctx.send(chat.info(_("Right now this user is doing nothing")))
            return
        await BaseMenu(ActivityPager(activities)).start(ctx)

    @commands.command(aliases=["servinfo", "serv", "sv"])
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def sinfo(self, ctx, *, server: commands.GuildConverter = None):
        """Shows server information"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        afk = server.afk_timeout / 60
        try:
            widget = await server.widget()
        except (discord.Forbidden, discord.HTTPException):
            widget = SimpleNamespace(invite_url=None)
        em = discord.Embed(
            title=_("Server info"),
            description=server.description and server.description or None,
            color=server.owner.color.value and server.owner.color or discord.Embed.Empty,
        )
        em.add_field(name=_("Name"), value=chat.escape(server.name, formatting=True))
        em.add_field(name=_("Server ID"), value=server.id)
        em.add_field(
            name=_("Exists since"),
            value=get_markdown_timestamp(server.created_at, TimestampStyle.datetime_long),
        )
        em.add_field(name=_("Region"), value=server.region)
        if server.preferred_locale:
            em.add_field(name=_("Discovery language"), value=server.preferred_locale)
        em.add_field(name=_("Owner"), value=chat.escape(str(server.owner), formatting=True))
        em.add_field(
            name=_("AFK timeout and channel"),
            value=_("{} min in {}").format(
                afk, chat.escape(str(server.afk_channel), formatting=True)
            ),
        )
        em.add_field(
            name=_("Verification level"),
            value=_("None")
            if server.verification_level == discord.VerificationLevel.none
            else _("Low")
            if server.verification_level == discord.VerificationLevel.low
            else _("Medium")
            if server.verification_level == discord.VerificationLevel.medium
            else _("High")
            if server.verification_level == discord.VerificationLevel.high
            else _("Highest")
            if server.verification_level == discord.VerificationLevel.extreme
            else _("Unknown"),
        )
        em.add_field(
            name=_("Explicit content filter"),
            value=_("Don't scan any messages.")
            if server.explicit_content_filter == discord.ContentFilter.disabled
            else _("Scan messages from members without a role.")
            if server.explicit_content_filter == discord.ContentFilter.no_role
            else _("Scan messages sent by all members.")
            if server.explicit_content_filter == discord.ContentFilter.all_members
            else _("Unknown"),
        )
        em.add_field(
            name=_("Default notifications"),
            value=_("All messages")
            if server.default_notifications == discord.NotificationLevel.all_messages
            else _("Only @mentions")
            if server.default_notifications == discord.NotificationLevel.only_mentions
            else _("Unknown"),
        )
        em.add_field(name=_("2FA admins"), value=bool_emojify(server.mfa_level))
        if server.rules_channel:
            em.add_field(
                name=_("Rules channel"),
                value=chat.escape(server.rules_channel.name, formatting=True),
            )
        if server.public_updates_channel:
            em.add_field(
                name=_("Public updates channel"),
                value=chat.escape(server.public_updates_channel.name, formatting=True),
            )
        if server.system_channel:
            em.add_field(
                name=_("System messages channel"),
                value=_(
                    "**Channel:** {channel}\n"
                    "**Welcome message:** {welcome}\n"
                    "**Boosts:** {boost}"
                ).format(
                    channel=chat.escape(server.system_channel.name, formatting=True),
                    welcome=bool_emojify(server.system_channel_flags.join_notifications),
                    boost=bool_emojify(server.system_channel_flags.premium_subscriptions),
                ),
                inline=False,
            )
        em.add_field(
            name=_("Stats"),
            value=_(
                "**Bot's shard:** {shard}\n"
                "**Member count:** {members}/{members_limit}\n"
                "**Role count:** {roles}/250\n"
                "**Channel count:** {channels}/500\n"
                "**Emoji count:** {emojis}/{emoji_limit}\n"
                "**Animated emoji count:** {animated_emojis}/{emoji_limit}\n"
                "**Boosters:** {boosters} ({boosts} **boosts**) (**Tier:** {tier}/3)\n"
                "**Max bitrate:** {bitrate} kbps\n"
                "**Max filesize:** {files} MB\n"
                "**Max users in voice with video:** {max_video}"
            ).format(
                shard=server.shard_id,
                members=server.member_count,
                members_limit=server.max_members or "100000",
                roles=len(server.roles),
                channels=len(server.channels),
                emojis=len([e for e in server.emojis if not e.animated]),
                animated_emojis=len([e for e in server.emojis if e.animated]),
                emoji_limit=server.emoji_limit,
                tier=server.premium_tier,
                boosters=len(server.premium_subscribers),
                boosts=server.premium_subscription_count,
                bitrate=server.bitrate_limit / 1000,
                files=server.filesize_limit / 1048576,
                max_video=server.max_video_channel_users,
            ),
            inline=False,
        )
        if server.features:
            em.add_field(
                name=_("Features"),
                value="\n".join(_(GUILD_FEATURES.get(f, f)) for f in server.features).format(
                    banner=server.banner and f" [🔗]({server.banner_url_as(format='png')})" or "",
                    splash=server.splash and f" [🔗]({server.splash_url_as(format='png')})" or "",
                    discovery=server.discovery_splash
                    and f" [🔗]({server.discovery_splash_url_as(format='png')})"
                    or "",
                ),
                inline=False,
            )
        roles_str = _("**Everyone role:** {}").format(server.default_role)
        if boost_role := server.premium_subscriber_role:
            roles_str += "\n" + _("**Booster role:** {}").format(boost_role)
        if bot_role := server.self_role:
            roles_str += "\n" + _("**{} role:** {}").format(ctx.me.display_name, bot_role)
        em.add_field(name=_("Roles"), value=roles_str, inline=False)
        if widget.invite_url:
            em.add_field(name=_("Widget's invite"), value=widget.invite_url)
        em.set_image(url=server.icon_url_as(static_format="png", size=4096))
        await ctx.send(embed=em)

    @commands.command()
    @commands.guild_only()
    @commands.mod_or_permissions(ban_members=True)
    @commands.bot_has_permissions(embed_links=True)
    async def bans(self, ctx: commands.Context, *, server: commands.GuildConverter = None):
        """Get bans from server by id"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        if not server.me.guild_permissions.ban_members:
            await ctx.send(_('I need permission "Ban Members" to access banned members on server'))
            return
        banlist = await server.bans()
        if banlist:
            banlisttext = "\n".join(f"{x.user} ({x.user.id})" for x in banlist)
            await BaseMenu(PagePager(list(chat.pagify(banlisttext)))).start(ctx)
        else:
            await ctx.send(_("Banlist is empty!"))

    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(embed_links=True)
    async def invites(self, ctx: commands.Context, *, server: commands.GuildConverter = None):
        """Get invites from server by id"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        if not server.me.guild_permissions.manage_guild:
            await ctx.send(
                _('I need permission "Manage Server" to access list of invites on server')
            )
            return
        invites = await server.invites()
        if invites:
            inviteslist = "\n".join(f"{x} ({x.channel.name})" for x in invites)
            await BaseMenu(PagePager(list(chat.pagify(inviteslist)))).start(ctx)
        else:
            await ctx.send(_("There is no invites for this server"))

    @commands.command(aliases=["chaninfo", "channelinfo"])
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def cinfo(
        self,
        ctx,
        *,
        channel: Union[
            discord.TextChannel,
            discord.VoiceChannel,
            discord.StageChannel,
            discord.CategoryChannel,
        ] = None,
    ):
        """Get info about channel"""
        if channel is None:
            channel = ctx.channel
        changed_roles = sorted(channel.changed_roles, key=lambda r: r.position, reverse=True)
        em = discord.Embed(
            title=chat.escape(str(channel.name), formatting=True),
            description=topic
            if (topic := getattr(channel, "topic", None))
            else "\N{SPEECH BALLOON}: {} | \N{SPEAKER}: {} | \N{SATELLITE ANTENNA}: {}".format(
                len(channel.text_channels),
                len(channel.voice_channels),
                len(channel.stage_channels),
            )
            if isinstance(channel, discord.CategoryChannel)
            else discord.Embed.Empty,
            color=await ctx.embed_color(),
        )
        em.add_field(name=_("ID"), value=channel.id)
        em.add_field(
            name=_("Type"),
            value=CHANNEL_TYPE_EMOJIS.get(channel.type, str(channel.type)),
        )
        em.add_field(
            name=_("Exists since"),
            value=get_markdown_timestamp(channel.created_at, TimestampStyle.datetime_long),
        )
        em.add_field(
            name=_("Category"),
            value=chat.escape(str(channel.category), formatting=True)
            or chat.inline(_("Not in category")),
        )
        em.add_field(name=_("Position"), value=channel.position)
        if isinstance(channel, discord.TextChannel):
            em.add_field(name=_("Users"), value=str(len(channel.members)))
        em.add_field(
            name=_("Changed roles permissions"),
            value=chat.escape(
                "\n".join(str(x) for x in changed_roles) or _("Not set"),
                formatting=True,
            ),
        )
        em.add_field(
            name=_("Mention"),
            value=f"{channel.mention}\n{chat.inline(channel.mention)}",
        )
        if isinstance(channel, discord.TextChannel):
            if channel.slowmode_delay:
                em.add_field(
                    name=_("Slowmode delay"),
                    value=_("{} seconds").format(channel.slowmode_delay),
                )
            em.add_field(name=_("NSFW"), value=bool_emojify(channel.is_nsfw()))
            if (
                channel.guild.me.permissions_in(channel).manage_webhooks
                and await channel.webhooks()
            ):
                em.add_field(name=_("Webhooks count"), value=str(len(await channel.webhooks())))
        elif isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            em.add_field(name=_("Region"), value=channel.rtc_region or _("Automatic"))
            em.add_field(name=_("Bitrate"), value=_("{}kbps").format(channel.bitrate / 1000))
            em.add_field(
                name=_("Users"),
                value=channel.user_limit
                and f"{len(channel.members)}/{channel.user_limit}"
                or f"{len(channel.members)}",
            )
            if isinstance(channel, discord.StageChannel):
                em.add_field(
                    name=_("Requesting to speak"),
                    value=_("{} users").format(len(channel.requesting_to_speak)),
                )
        elif isinstance(channel, discord.CategoryChannel):
            em.add_field(name=_("NSFW"), value=bool_emojify(channel.is_nsfw()))
        await ctx.send(embed=em)

    @commands.command(aliases=["channellist", "listchannels"])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_channels=True)
    @commands.bot_has_permissions(embed_links=True)
    async def channels(self, ctx, *, server: commands.GuildConverter = None):
        """Get all channels on server"""
        # TODO: Use dpy menus for that
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        channels = {
            channel_type: ChannelsPager(getattr(server, type_data[0]))
            for channel_type, type_data in KNOWN_CHANNEL_TYPES.items()
        }
        await ChannelsMenu(channels, "category", len(server.channels)).start(ctx)

    @commands.command(aliases=["roleinfo"])
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def rinfo(self, ctx, *, role: discord.Role):
        """Get info about role"""
        em = discord.Embed(
            title=chat.escape(role.name, formatting=True),
            color=role.color if role.color.value else discord.Embed.Empty,
        )
        em.add_field(name=_("ID"), value=role.id)
        em.add_field(
            name=_("Permissions"),
            value="[{0}](https://cogs.fixator10.ru/permissions-calculator/?v={0})".format(
                role.permissions.value
            ),
        )
        em.add_field(
            name=_("Exists since"),
            value=get_markdown_timestamp(role.created_at, TimestampStyle.datetime_long),
        )
        em.add_field(name=_("Color"), value=role.colour)
        em.add_field(name=_("Members"), value=str(len(role.members)))
        em.add_field(name=_("Position"), value=role.position)
        em.add_field(name=_("Managed"), value=bool_emojify(role.managed))
        em.add_field(name=_("Managed by bot"), value=bool_emojify(role.is_bot_managed()))
        em.add_field(name=_("Managed by boosts"), value=bool_emojify(role.is_premium_subscriber()))
        em.add_field(name=_("Managed by integration"), value=bool_emojify(role.is_integration()))
        em.add_field(name=_("Hoist"), value=bool_emojify(role.hoist))
        em.add_field(name=_("Mentionable"), value=bool_emojify(role.mentionable))
        em.add_field(name=_("Mention"), value=role.mention + "\n`" + role.mention + "`")
        em.set_thumbnail(
            url=f"https://xenforo.com/community/rgba.php?r={role.colour.r}&g={role.color.g}&b={role.color.b}&a=255"
        )
        await ctx.send(embed=em)

    @commands.command()
    @commands.guild_only()
    async def rolemembers(self, ctx, *, role: discord.Role):
        """Get list of members that has provided role"""
        memberslist = [(m.id, str(m)) for m in sorted(role.members, key=lambda m: m.joined_at)]
        if not memberslist:
            await ctx.send(chat.error(_("There is no members in this role")))
            return
        await BaseMenu(
            PagePager(
                list(
                    chat.pagify(
                        tabulate.tabulate(
                            memberslist, tablefmt="orgtbl", headers=[_("ID"), _("Name")]
                        )
                    )
                )
            )
        ).start(ctx)

    @commands.command(aliases=["listroles", "rolelist"])
    @commands.admin_or_permissions(manage_roles=True)
    @commands.guild_only()
    async def roles(self, ctx, *, server: commands.GuildConverter = None):
        """Get all roles on server"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        roles = [(role.id, shorten(role.name, 32, placeholder="…")) for role in server.roles]
        await BaseMenu(
            PagePager(
                list(
                    chat.pagify(
                        tabulate.tabulate(roles, tablefmt="orgtbl", headers=[_("ID"), _("Name")])
                    )
                )
            )
        ).start(ctx)

    @commands.command(aliases=["cperms"])
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def chanperms(
        self,
        ctx,
        member: Optional[discord.Member],
        *,
        channel: Union[
            discord.TextChannel,
            discord.VoiceChannel,
            discord.StageChannel,
            discord.CategoryChannel,
        ] = None,
    ):
        """Check user's permission for current or provided channel"""
        if not member:
            member = ctx.author
        if not channel:
            channel = ctx.channel
        perms = channel.permissions_for(member)
        await ctx.send(
            "{}\n{}".format(
                chat.inline(str(perms.value)),
                chat.box(
                    chat.format_perms_list(perms) if perms.value else _("No permissions"),
                    lang="py",
                ),
            )
        )

    @commands.command(aliases=["emojiinfo", "emojinfo"])
    @commands.bot_has_permissions(embed_links=True)
    async def einfo(self, ctx, *, emoji: Union[discord.Emoji, discord.PartialEmoji] = None):
        """Get info about emoji"""
        if not emoji:
            if ctx.channel.permissions_for(ctx.author).add_reactions:
                m = await ctx.send(_("React to this message with your emoji"))
                try:
                    reaction = await ctx.bot.wait_for(
                        "reaction_add",
                        check=ReactionPredicate.same_context(message=m, user=ctx.author),
                        timeout=30,
                    )
                    emoji = reaction[0].emoji
                except AsyncTimeoutError:
                    return
                finally:
                    await m.delete(delay=0)
            else:
                await ctx.send_help()
                return
        em = await emoji_embed(ctx, emoji)
        await ctx.send(embed=em)

    @commands.command(aliases=["emojilist", "listemojis"])
    @commands.guild_only()
    async def emojis(self, ctx, *, server: commands.GuildConverter = None):
        """Get all emojis on server"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        if not (emojis := server.emojis):
            await ctx.send(_("No emojis on this server"))
            return
        await BaseMenu(EmojiPager(emojis)).start(ctx)
