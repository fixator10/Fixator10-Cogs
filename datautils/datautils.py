from asyncio import TimeoutError as AsyncTimeoutError
from textwrap import shorten
from typing import Union
from types import SimpleNamespace
import unicodedata

import discord
import tabulate
from redbot.core import checks
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


def bool_emojify(bool_var: bool) -> str:
    return "✅" if bool_var else "❌"


_ = Translator("DataUtils", __file__)


TWEMOJI_URL = "https://twemoji.maxcdn.com/v/latest/72x72"


GUILD_FEATURES = {
    "VIP_REGIONS": _("VIP voice regions"),
    "VANITY_URL": _("Vanity invite URL"),
    "INVITE_SPLASH": _("Invite splash{splash}"),
    "VERIFIED": _("Verified"),
    "PARTNERED": _("Discord Partner"),
    "MORE_EMOJI": _("Extended emoji limit"),  # Non-boosted?
    "DISCOVERABLE": _("Shows in Server Discovery{discovery}"),
    "COMMERCE": _("Store channels"),
    "PUBLIC": _('"Lurkable"'),
    "NEWS": _("News channels"),
    "BANNER": _("Banner{banner}"),
    "ANIMATED_ICON": _("Animated icon"),
    "PUBLIC_DISABLED": _("Cannot be public"),
}

ACTIVITY_TYPES = {
    discord.ActivityType.playing: _("Playing"),
    discord.ActivityType.watching: _("Watching"),
    discord.ActivityType.listening: _("Listening"),
}


async def get_twemoji(emoji: str):
    emoji_unicode = []
    for char in emoji:
        char = hex(ord(char))[2:]
        if char != "fe0f":  # Variation Selector-16
            emoji_unicode.append(char)
    emoji_unicode = "-".join(emoji_unicode)
    return f"{TWEMOJI_URL}/{emoji_unicode}.png"


@cog_i18n(_)
class DataUtils(commands.Cog):
    __version__ = "2.2.8"

    # noinspection PyMissingConstructor
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.TIME_FORMAT = _("%d.%m.%Y %H:%M:%S %Z")

    @commands.command(aliases=["fetchuser"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @checks.bot_has_permissions(embed_links=True)
    async def getuserinfo(self, ctx, user_id: int):
        """Get info about any Discord's user by ID"""
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            await ctx.send(
                chat.error(_("Discord user with ID `{}` not found").format(user_id))
            )
            return
        except discord.HTTPException:
            await ctx.send(
                chat.warning(
                    _(
                        "I was unable to get data about user with ID `{}`. Try again later"
                    ).format(user_id)
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
                value=f"[`{user.avatar}`]({user.avatar_url_as(static_format='png', size=2048)})",
            )
        em.set_image(url=user.avatar_url_as(static_format="png", size=2048))
        em.set_thumbnail(url=user.default_avatar_url)
        em.set_footer(text=_("Created at"))
        await ctx.send(embed=em)

    @commands.command(aliases=["memberinfo", "membinfo"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def uinfo(self, ctx, *, member: discord.Member = None):
        """Information on a user"""
        if member is None:
            member = ctx.message.author
        em = discord.Embed(
            title=chat.escape(str(member), formatting=True),
            color=member.color.value and member.color or discord.Embed.Empty,
        )
        member.nick and em.add_field(
            name=_("Nickname"), value=member.nick
        ) or em.add_field(name=_("Name"), value=member.name)
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
            name=_("Joined server"), value=member.joined_at.strftime(self.TIME_FORMAT)
        )
        em.add_field(name="ID", value=member.id)
        em.add_field(
            name=_("Has existed since"),
            value=member.created_at.strftime(self.TIME_FORMAT),
        )
        member.color.value and em.add_field(name=_("Color"), value=member.colour)
        member.premium_since and em.add_field(
            name=_("Boosted server"),
            value=member.premium_since.strftime(self.TIME_FORMAT),
        )
        em.add_field(name=_("Bot?"), value=bool_emojify(member.bot))
        em.add_field(name=_("System?"), value=bool_emojify(member.system))
        em.add_field(
            name=_("Server permissions"),
            value="[{0}](https://discordapi.com/permissions.html#{0})".format(
                member.guild_permissions.value
            ),
        )
        member.voice and em.add_field(
            name=_("In voice channel"), value=member.voice.channel.mention
        )
        em.add_field(
            name=_("Mention"),
            value=f"{member.mention}\n{chat.inline(member.mention)}",
            inline=False,
        )
        em.add_field(
            name=_("Roles"),
            value="\n".join(
                [role.name for role in member.roles if not role.is_default()]
            )
            or "❌",
            inline=False,
        )
        em.set_image(url=member.avatar_url_as(static_format="png", size=2048))
        # em.set_thumbnail(url=member.default_avatar_url)
        await ctx.send(embed=em)

    @commands.command(aliases=["activity"])
    @commands.guild_only()
    @checks.mod_or_permissions(embed_links=True)
    async def activities(self, ctx, *, member: discord.Member = None):
        """List user's activities"""
        if member is None:
            member = ctx.message.author
        pages = []
        for activity in member.activities:
            em = await self.activity_embed(ctx, activity)
            pages.append(em)
        if pages:
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            await ctx.send(chat.info(_("Right now this user is doing nothing")))

    @commands.command(aliases=["servinfo", "serv", "sv"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def sinfo(self, ctx, *, server: int = None):
        """Shows server information"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        else:
            server = self.bot.get_guild(server)
        if server is None:
            await ctx.send(_("Failed to get server with provided ID"))
            return
        afk = server.afk_timeout / 60
        try:
            widget = await server.widget()
        except (discord.Forbidden, discord.HTTPException):
            widget = SimpleNamespace(invite_url=None)
        em = discord.Embed(
            title=_("Server info"),
            description=server.description and server.description or None,
            color=server.owner.color.value
            and server.owner.color
            or discord.Embed.Empty,
        )
        em.add_field(name=_("Name"), value=chat.escape(server.name, formatting=True))
        em.add_field(name=_("Server ID"), value=server.id)
        em.add_field(
            name=_("Existed since"), value=server.created_at.strftime(self.TIME_FORMAT)
        )
        em.add_field(name=_("Region"), value=server.region)
        server.preferred_locale and em.add_field(
            name=_("Discovery language"), value=server.preferred_locale
        )
        em.add_field(
            name=_("Owner"), value=chat.escape(str(server.owner), formatting=True)
        )
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
            else _("(╯°□°）╯︵ ┻━┻")
            if server.verification_level == discord.VerificationLevel.high
            else _("┻━┻ ﾐヽ(ಠ益ಠ)ノ彡┻━┻")
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
        server.system_channel and em.add_field(
            name=_("System messages channel"),
            value=_(
                "**Channel:** {channel}\n"
                "**Welcome message:** {welcome}\n"
                "**Boosts:** {boost}"
            ).format(
                channel=chat.escape(str(server.system_channel), formatting=True),
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
                "**Max filesize:** {files} MB"
            ).format(
                shard=server.shard_id,
                members=server.member_count,
                members_limit=server.max_members or "250000",
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
            ),
            inline=False,
        )
        server.features and em.add_field(
            name=_("Features"),
            value="\n".join(GUILD_FEATURES.get(f, f) for f in server.features).format(
                banner=server.banner
                and f" [🔗]({server.banner_url_as(format='png')})"
                or "",
                splash=server.splash
                and f" [🔗]({server.splash_url_as(format='png')})"
                or "",
                discovery=server.discovery_splash
                and f" [🔗]({server.discovery_splash_url_as(format='png')})"
                or "",
            ),
            inline=False,
        )
        widget.invite_url and em.add_field(
            name=_("Widget's invite"), value=widget.invite_url
        )
        em.set_image(url=server.icon_url_as(format="png", size=2048))
        await ctx.send(embed=em)

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(ban_members=True)
    @checks.bot_has_permissions(embed_links=True)
    async def bans(self, ctx: commands.Context, *, server: int = None):
        """Get bans from server by id"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        else:
            server = self.bot.get_guild(server)
        if server is None:
            await ctx.send(_("Failed to get server with provided ID"))
            return
        if not server.me.guild_permissions.ban_members:
            await ctx.send(
                _('I need permission "Ban Members" to access banned members on server')
            )
            return
        banlist = await server.bans()
        if banlist:
            banlisttext = "\n".join([f"{x.user} ({x.user.id})" for x in banlist])
            pages = [chat.box(page) for page in list(chat.pagify(banlisttext))]
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            await ctx.send(_("Banlist is empty!"))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    @checks.bot_has_permissions(embed_links=True)
    async def invites(self, ctx: commands.Context, *, server: int = None):
        """Get invites from server by id"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        else:
            server = self.bot.get_guild(server)
        if server is None:
            await ctx.send(_("Failed to get server with provided ID"))
            return
        if not server.me.guild_permissions.manage_guild:
            await ctx.send(
                _(
                    'I need permission "Manage Server" to access list of invites on server'
                )
            )
            return
        invites = await server.invites()
        if invites:
            inviteslist = "\n".join([f"{x} ({x.channel.name})" for x in invites])
            await menu(ctx, list(chat.pagify(inviteslist)), DEFAULT_CONTROLS)
        else:
            await ctx.send(_("There is no invites for this server"))

    @commands.command(aliases=["chaninfo", "channelinfo"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def cinfo(
        self,
        ctx,
        *,
        channel: Union[
            discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel, None
        ] = None,
    ):
        """Get info about channel"""
        if channel is None:
            channel = ctx.channel
        changed_roles = sorted(
            channel.changed_roles, key=lambda r: r.position, reverse=True
        )
        em = discord.Embed(
            title=chat.escape(str(channel.name), formatting=True),
            description=channel.topic
            if isinstance(channel, discord.TextChannel)
            else "💬: {} | 🔈: {}".format(
                len(channel.text_channels), len(channel.voice_channels)
            )
            if isinstance(channel, discord.CategoryChannel)
            else None,
            color=await ctx.embed_color(),
        )
        em.add_field(name=_("ID"), value=channel.id)
        em.add_field(
            name=_("Type"),
            value="🔈"
            if isinstance(channel, discord.VoiceChannel)
            else "💬"
            if isinstance(channel, discord.TextChannel)
            else "📑"
            if isinstance(channel, discord.CategoryChannel)
            else "❔",
        )
        em.add_field(
            name=_("Has existed since"),
            value=channel.created_at.strftime(self.TIME_FORMAT),
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
            value="\n".join([str(x) for x in changed_roles]) or _("Not set"),
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
                em.add_field(
                    name=_("Webhooks count"), value=str(len(await channel.webhooks()))
                )
        elif isinstance(channel, discord.VoiceChannel):
            em.add_field(
                name=_("Bitrate"), value=_("{}kbps").format(channel.bitrate / 1000)
            )
            em.add_field(
                name=_("Users"),
                value=channel.user_limit
                and f"{len(channel.members)}/{channel.user_limit}"
                or f"{len(channel.members)}",
            )
        elif isinstance(channel, discord.CategoryChannel):
            em.add_field(name=_("NSFW"), value=bool_emojify(channel.is_nsfw()))
        await ctx.send(embed=em)

    @commands.command(aliases=["channellist", "listchannels"])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_channels=True)
    @checks.bot_has_permissions(embed_links=True)
    async def channels(self, ctx, *, server: int = None):
        """Get all channels on server"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        else:
            server = discord.utils.get(self.bot.guilds, id=server)
        if server is None:
            await ctx.send(_("Failed to get server with provided ID"))
            return
        categories = "\n".join(
            [chat.escape(x.name, formatting=True) for x in server.categories]
        ) or _("No categories")
        text_channels = "\n".join(
            [chat.escape(x.name, formatting=True) for x in server.text_channels]
        ) or _("No text channels")
        voice_channels = "\n".join(
            [chat.escape(x.name, formatting=True) for x in server.voice_channels]
        ) or _("No voice channels")
        em = discord.Embed(title=_("Channels list"), color=await ctx.embed_color())
        em.add_field(name=_("Categories:"), value=categories, inline=False)
        em.add_field(name=_("Text channels:"), value=text_channels, inline=False)
        em.add_field(name=_("Voice channels:"), value=voice_channels, inline=False)
        em.set_footer(
            text=_(
                "Total count of channels: {} • "
                "Categories: {} • "
                "Text Channels: {} • "
                "Voice Channels: {}"
            ).format(
                len(server.channels),
                len(server.categories),
                len(server.text_channels),
                len(server.voice_channels),
            )
        )
        await ctx.send(embed=em)

    @commands.command(aliases=["roleinfo"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def rinfo(self, ctx, *, role: discord.Role):
        """Get info about role"""
        em = discord.Embed(
            title=chat.escape(role.name, formatting=True),
            color=role.color.value and role.color or discord.Embed.Empty,
        )
        em.add_field(name=_("ID"), value=role.id)
        em.add_field(
            name=_("Permissions"),
            value="[{0}](https://discordapi.com/permissions.html#{0})".format(
                role.permissions.value
            ),
        )
        em.add_field(
            name=_("Has existed since"),
            value=role.created_at.strftime(self.TIME_FORMAT),
        )
        em.add_field(name=_("Hoist"), value=bool_emojify(role.hoist))
        em.add_field(name=_("Members"), value=str(len(role.members)))
        em.add_field(name=_("Position"), value=role.position)
        em.add_field(name=_("Color"), value=role.colour)
        em.add_field(name=_("Managed"), value=bool_emojify(role.managed))
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
        memberslist = [str(m) for m in sorted(role.members, key=lambda m: m.joined_at)]
        if not memberslist:
            await ctx.send(chat.error(_("There is no members in this role")))
            return
        pages = [
            discord.Embed(description=p, color=await ctx.embed_color())
            for p in chat.pagify("\n".join(memberslist), page_length=2048)
        ]
        pagenum = 1
        for page in pages:
            page.set_footer(text=_("Page {}/{}").format(pagenum, len(pages)))
            pagenum += 1
        await menu(ctx, pages, DEFAULT_CONTROLS)

    @commands.command(aliases=["listroles", "rolelist"])
    @commands.admin_or_permissions(manage_roles=True)
    @commands.guild_only()
    async def roles(self, ctx, server: int = None):
        """Get all roles on server"""
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        else:
            server = self.bot.get_guild(server)
        if server is None:
            await ctx.send(_("Failed to get server with provided ID"))
            return
        roles = []
        for role in server.roles:
            dic = {_("Name"): shorten(role.name, 32, placeholder="…"), _("ID"): role.id}
            roles.append(dic)
        pages = list(chat.pagify(tabulate.tabulate(roles, tablefmt="orgtbl")))
        pages = [chat.box(p) for p in pages]
        await menu(ctx, pages, DEFAULT_CONTROLS)

    @commands.command(aliases=["cperms"])
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def chanperms(
        self,
        ctx,
        member: discord.Member,
        *,
        channel: Union[
            discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel, None
        ] = None,
    ):
        """Check user's permission for current or provided channel"""
        if channel is None:
            channel = ctx.channel
        perms = channel.permissions_for(member)
        await ctx.send(
            "{}\n{}".format(
                chat.inline(str(member.guild_permissions.value)),
                chat.box(chat.format_perms_list(perms), lang="py"),
            )
        )

    @commands.command(aliases=["emojiinfo", "emojinfo"])
    @checks.bot_has_permissions(embed_links=True)
    async def einfo(
        self, ctx, *, emoji: Union[discord.Emoji, discord.PartialEmoji] = None
    ):
        """Get info about emoji"""
        if emoji is None:
            if ctx.channel.permissions_for(ctx.author).add_reactions:
                m = await ctx.send(_("React to this message with your emoji"))
                try:
                    reaction = await ctx.bot.wait_for(
                        "reaction_add",
                        check=ReactionPredicate.same_context(
                            message=m, user=ctx.author
                        ),
                        timeout=30,
                    )
                    emoji = reaction[0].emoji
                except AsyncTimeoutError:
                    return
                finally:
                    await m.delete()
            else:
                await ctx.send_help()
                return
        em = await self.emoji_embed(ctx, emoji)
        await ctx.send(embed=em)

    @commands.command(aliases=["emojilist", "listemojis"])
    @commands.guild_only()
    async def emojis(self, ctx, server: int = None):
        if server is None or not await self.bot.is_owner(ctx.author):
            server = ctx.guild
        else:
            server = self.bot.get_guild(server)
        if server is None:
            await ctx.send(_("Failed to get server with provided ID"))
            return
        emojis = [await self.emoji_embed(ctx, emoji) for emoji in server.emojis]
        pagenum = 1
        for page in emojis:
            page.set_footer(text=_("Page {}/{}").format(pagenum, len(emojis)))
            pagenum += 1
        if emojis:
            await menu(ctx, emojis, DEFAULT_CONTROLS)
        else:
            await ctx.send(_("No emojis on this server"))

    async def emoji_embed(self, ctx, emoji: Union[discord.Emoji, discord.PartialEmoji]):
        """Make embed with info about emoji"""
        em = discord.Embed(
            title=isinstance(emoji, str)
            and unicodedata.name(emoji[0], f"\\{emoji}")
            or chat.escape(emoji.name, formatting=True),
            color=await ctx.embed_color(),
        )
        if isinstance(emoji, str):
            # TODO: Support for multicharacter emojis
            emoji = emoji[0]
            # em.add_field(name=_("Unicode emoji"), value="✅")
            em.add_field(name=_("Unicode character"), value=f"\\{emoji}")
            em.add_field(name=_("Unicode category"), value=unicodedata.category(emoji))
            em.set_image(url=await get_twemoji(emoji))
        if not isinstance(emoji, str):
            em.add_field(name=_("ID"), value=emoji.id)
            em.add_field(name=_("Animated"), value=bool_emojify(emoji.animated))
            em.set_image(url=emoji.url)
        if isinstance(emoji, discord.Emoji):
            em.add_field(
                name=_("Has existed since"),
                value=emoji.created_at.strftime(self.TIME_FORMAT),
            )
            em.add_field(
                name=_('":" required'), value=bool_emojify(emoji.require_colons)
            )
            em.add_field(name=_("Managed"), value=bool_emojify(emoji.managed))
            em.add_field(name=_("Server"), value=emoji.guild)
            if emoji.roles:
                em.add_field(
                    name=_("Roles"), value="\n".join([x.name for x in emoji.roles])
                )
        elif isinstance(emoji, discord.PartialEmoji):
            em.add_field(
                name=_("Has existed since"),
                value=discord.utils.snowflake_time(emoji.id).strftime(self.TIME_FORMAT),
            )
            em.add_field(
                name=_("Custom emoji"), value=bool_emojify(emoji.is_custom_emoji())
            )
            # em.add_field(
            #     name=_("Unicode emoji"), value=bool_emojify(emoji.is_unicode_emoji())
            # )
        return em

    async def activity_embed(self, ctx, activity: discord.Activity):
        """Make embed with info about emoji"""
        # design is not my best side
        if isinstance(activity, discord.CustomActivity):
            em = discord.Embed(title=activity.name, color=await ctx.embed_color())
            if activity.emoji:
                if activity.emoji.is_unicode_emoji():
                    emoji_pic = await get_twemoji(activity.emoji.name)
                else:
                    emoji_pic = activity.emoji.url
                if activity.name:
                    em.set_thumbnail(url=emoji_pic)
                else:
                    em.set_image(url=emoji_pic)
            em.set_footer(text=_("Custom status"))
        elif isinstance(activity, discord.Game):
            em = discord.Embed(
                title=_("Playing {}").format(activity.name),
                timestamp=activity.start or discord.Embed.Empty,
                color=await ctx.embed_color(),
            )
            activity.end and em.add_field(
                name=_("This game will end at"),
                value=activity.end.strftime(self.TIME_FORMAT),
            )
            activity.start and em.set_footer(text=_("Playing since"))
        elif isinstance(activity, discord.Activity):
            party_size = activity.party.get("size")
            party_size = party_size and f" ({party_size[0]}/{party_size[1]})" or ""
            em = discord.Embed(
                title=f"{ACTIVITY_TYPES.get(activity.type, activity.type)} {activity.name}",
                description=f"{activity.details and activity.details or ''}\n"
                f"{activity.state and activity.state or ''}{party_size}",
                color=await ctx.embed_color(),
            )
            activity.small_image_text and em.add_field(
                name=_("Small image text"),
                value=activity.small_image_text,
                inline=False,
            )
            activity.application_id and em.add_field(
                name=_("Application ID"), value=activity.application_id
            )
            activity.start and em.add_field(
                name=_("Started at"), value=activity.start.strftime(self.TIME_FORMAT),
            )
            activity.end and em.add_field(
                name=_("Will end at"), value=activity.end.strftime(self.TIME_FORMAT),
            )
            activity.large_image_text and em.add_field(
                name=_("Large image text"),
                value=activity.large_image_text,
                inline=False,
            )
            activity.small_image_url and em.set_thumbnail(url=activity.small_image_url)
            activity.large_image_url and em.set_image(url=activity.large_image_url)
        elif isinstance(activity, discord.Streaming):
            em = discord.Embed(
                title=activity.name,
                description=_("Streaming on {}").format(activity.platform),
                url=activity.url,
            )
            activity.game and em.add_field(name=_("Game"), value=activity.game)
        elif isinstance(activity, discord.Spotify):
            em = discord.Embed(
                title=activity.title,
                description=_("by {}\non {}").format(
                    ", ".join(activity.artists), activity.album
                ),
                color=activity.color,
                timestamp=activity.created_at,
                url=f"https://open.spotify.com/track/{activity.track_id}",
            )
            em.add_field(
                name=_("Started at"), value=activity.start.strftime(self.TIME_FORMAT)
            )
            em.add_field(
                name=_("Duration"), value=str(activity.duration)[:-3]
            )  # 0:03:33.877[000]
            em.add_field(
                name=_("Will end at"), value=activity.end.strftime(self.TIME_FORMAT)
            )
            em.set_image(url=activity.album_cover_url)
            em.set_footer(text=_("Listening since"))
        else:
            em = discord.Embed(
                title=_("Unsupported activity type: {}").format(type(activity))
            )
        return em