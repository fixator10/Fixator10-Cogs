from typing import Union

import discord
import matplotlib.colors as colors
import tabulate
from redbot.core import checks
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


def rgb_to_hex(rgb_tuple):
    return colors.rgb2hex([1.0 * x / 255 for x in rgb_tuple])


def bool_emojify(bool_var: bool) -> str:
    return "✅" if bool_var else "❌"


_ = Translator("DataUtils", __file__)


@cog_i18n(_)
class DataUtils(commands.Cog):
    # noinspection PyMissingConstructor
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.TIME_FORMAT = _("%d.%m.%Y %H:%M:%S %Z")

    @commands.command(alias=["fetchuser"])
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
        embed = discord.Embed(
            title=chat.escape(str(user), formatting=True),
            timestamp=user.created_at,
            color=await ctx.embed_color(),
        )
        embed.add_field(name=_("ID"), value=user.id)
        embed.add_field(name=_("Bot?"), value=bool_emojify(user.bot))
        embed.add_field(name=_("Mention"), value=user.mention)
        embed.add_field(
            name=_("Default avatar"),
            value=f"[{user.default_avatar}]({user.default_avatar_url})",
        )
        if user.avatar:
            embed.add_field(
                name=_("Avatar"),
                value=f"[`{user.avatar}`]({user.avatar_url_as(static_format='png', size=2048)})",
            )
        embed.set_image(url=user.avatar_url_as(static_format="png", size=2048))
        embed.set_thumbnail(url=user.default_avatar_url)
        embed.set_footer(text=_("Created at"))
        await ctx.send(embed=embed)

    @commands.command(aliases=["memberinfo", "membinfo"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def uinfo(self, ctx, *, member: discord.Member = None):
        """Information on a user"""
        if member is None:
            member = ctx.message.author
        em = discord.Embed(
            title=member.nick and chat.escape(member.nick, formatting=True) or None,
            color=member.color.value and member.color or discord.Embed.Empty,
        )
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
            name=_("Joined server"), value=member.joined_at.strftime(self.TIME_FORMAT)
        )
        em.add_field(name="ID", value=member.id)
        em.add_field(
            name=_("Has existed since"),
            value=member.created_at.strftime(self.TIME_FORMAT),
        )
        if member.color.value:
            em.add_field(name=_("Color"), value=member.colour)
        em.add_field(name=_("Bot?"), value=bool_emojify(member.bot))
        em.add_field(
            name=_("Server permissions"),
            value="[{0}](https://discordapi.com/permissions.html#{0})".format(
                member.guild_permissions.value
            ),
        )
        em.add_field(
            name=_("Mention"), value=f"{member.mention}\n{chat.inline(member.mention)}"
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
        em.set_thumbnail(
            url=f"https://xenforo.com/community/rgba.php"
            f"?r={member.colour.r}"
            f"&g={member.colour.g}"
            f"&b={member.colour.b}"
            f"&a=255"
        )
        await ctx.send(embed=em)

    @commands.command(aliases=["servinfo", "serv", "sv"])
    @commands.guild_only()
    @checks.is_owner()
    @checks.bot_has_permissions(embed_links=True)
    async def sinfo(self, ctx, *, server: int = None):
        """Shows server information"""
        if server is None:
            server = ctx.guild
        else:
            server = self.bot.get_guild(server)
        if server is None:
            await ctx.send(_("Failed to get server with provided ID"))
            return
        afk = server.afk_timeout / 60
        vip_regs = bool_emojify("VIP_REGIONS" in server.features)
        van_url = bool_emojify("VANITY_URL" in server.features)
        verified = bool_emojify("VERIFIED" in server.features)
        emoji_ext = bool_emojify("MORE_EMOJI" in server.features)
        inv_splash = "INVITE_SPLASH" in server.features
        em = discord.Embed(
            title=_("Server info"),
            color=server.owner.color.value
            and server.owner.color
            or discord.Embed.Empty,
        )
        em.add_field(name=_("Name"), value=chat.escape(server.name, formatting=True))
        em.add_field(name=_("Server ID"), value=server.id)
        em.add_field(name=_("Region"), value=server.region)
        em.add_field(
            name=_("Existed since"), value=server.created_at.strftime(self.TIME_FORMAT)
        )
        em.add_field(
            name=_("Owner"), value=chat.escape(str(server.owner), formatting=True)
        )
        em.add_field(
            name=_("AFK Timeout and Channel"),
            value=_("{} min in {}").format(
                afk, chat.escape(str(server.afk_channel), formatting=True)
            ),
        )
        em.add_field(
            name=_("New member messages channel"),
            value=chat.escape(str(server.system_channel), formatting=True),
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
        em.add_field(name=_("Member Count"), value=server.member_count)
        em.add_field(name=_("Role Count"), value=str(len(server.roles)))
        em.add_field(name=_("Channel Count"), value=str(len(server.channels)))
        em.add_field(name=_("VIP Voice Regions"), value=vip_regs)
        em.add_field(name=_("Vanity URL"), value=van_url)
        em.add_field(name=_("Verified"), value=verified)
        em.add_field(name=_("Extended emoji limit"), value=emoji_ext)
        if not inv_splash:
            em.add_field(name=_("Invite Splash"), value="❌")
        elif not server.splash_url:
            em.add_field(name=_("Invite Splash"), value="✅")
        else:
            em.add_field(
                name=_("Invite Splash"),
                value=f"✅ [🔗]({server.splash_url_as(format='png', size=2048)})",
            )
        if server.banner:
            em.add_field(
                name=_("Banner"),
                value=f"✅ [🔗]({server.banner_url_as(format='png', size=2048)})",
            )
        else:
            em.add_field(name=_("Banner"), value="❌")
        em.set_image(url=server.icon_url_as(format="png", size=2048))
        await ctx.send(embed=em)

    @commands.command()
    @commands.guild_only()
    @checks.is_owner()
    @checks.bot_has_permissions(embed_links=True)
    async def bans(self, ctx: commands.Context, *, server: int = None):
        """Get bans from server by id"""
        if server is None:
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
    @checks.is_owner()
    @checks.bot_has_permissions(embed_links=True)
    async def invites(self, ctx: commands.Context, *, server: int = None):
        """Get invites from server by id"""
        if server is None:
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
    @checks.is_owner()
    @checks.bot_has_permissions(embed_links=True)
    async def channels(self, ctx, *, server: int = None):
        """Get all channels on server"""
        if server is None:
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
    @commands.guild_only()
    @checks.is_owner()
    async def roles(self, ctx, server: int = None):
        """Get all roles on server"""
        if server is None:
            server = ctx.guild
        else:
            server = self.bot.get_guild(server)
        if server is None:
            await ctx.send(_("Failed to get server with provided ID"))
            return
        roles = []
        for role in server.roles:
            dic = {_("Name"): await self.smart_truncate(role.name), _("ID"): role.id}
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
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def einfo(
        self, ctx, *, emoji: Union[discord.Emoji, discord.PartialEmoji, None]
    ):
        """Get info about emoji"""
        if emoji is None:
            await ctx.send_help()
            return
        em = discord.Embed(
            title=chat.escape(emoji.name, formatting=True),
            color=await ctx.embed_color(),
        )
        em.add_field(name=_("ID"), value=emoji.id)
        em.add_field(name=_("Animated"), value=bool_emojify(emoji.animated))
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
                name=_("Custom emoji"), value=bool_emojify(emoji.is_custom_emoji())
            )
            em.add_field(
                name=_("Unicode emoji"), value=bool_emojify(emoji.is_unicode_emoji())
            )
        em.set_image(url=emoji.url)
        await ctx.send(embed=em)

    async def smart_truncate(self, content, length=32, suffix="…"):
        """https://stackoverflow.com/questions/250357/truncate-a-string-without-ending-in-the-middle-of-a-word"""
        content_str = str(content)
        if len(content_str) <= length:
            return content
        return " ".join(content_str[: length + 1].split(" ")[0:-1]) + suffix
