from asyncio import TimeoutError as AsyncTimeoutError
from textwrap import shorten
from typing import Union

import aiohttp
import discord
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.mod import get_audit_reason
from redbot.core.utils.predicates import ReactionPredicate
from tabulate import tabulate

from .discord_py_future import edit_role_icon

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json

_ = Translator("PersonalRoles", __file__)


async def has_assigned_role(ctx):
    """Check if user has assigned role"""
    return ctx.guild.get_role(await ctx.cog.config.member(ctx.author).role())


async def role_icons_feature(ctx):
    """Check for ROLE_ICONS feature"""
    return "ROLE_ICONS" in ctx.guild.features


@cog_i18n(_)
class PersonalRoles(commands.Cog):
    """Assign and edit personal roles"""

    __version__ = "2.2.2"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(json_serialize=json.dumps)
        self.config = Config.get_conf(self, identifier=0x3D86BBD3E2B744AE8AA8B5D986EB4DD8)
        default_member = {"role": None}
        default_guild = {"blacklist": [], "role_persistence": True}
        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)

        # Set cooldown for `[p]myrole icon` commands
        self._icon_cd = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        for cmd in self.icon.walk_commands():
            cmd._buckets = self._icon_cd

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        # Thanks Sinbad
        data = await self.config.all_members()
        async for guild_id, members in AsyncIter(data.items()):
            if user_id in members:
                await self.config.member_from_ids(guild_id, user_id).clear()

    @commands.group()
    @commands.guild_only()
    async def myrole(self, ctx):
        """Control of personal role"""
        pass

    @myrole.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def assign(self, ctx, user: discord.Member, *, role: discord.Role):
        """Assign personal role to someone"""
        await self.config.member(user).role.set(role.id)
        await ctx.send(
            _(
                "Ok. I just assigned {user.name} ({user.id}) to role {role.name} ({role.id})."
            ).format(user=user, role=role)
        )

    @myrole.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def unassign(self, ctx, *, user: Union[discord.Member, discord.User, int]):
        """Unassign personal role from someone"""
        if isinstance(user, discord.Member):
            await self.config.member(user).role.clear()
        elif isinstance(user, int):
            await self.config.member_from_ids(ctx.guild.id, user).role.clear()
            if _user := self.bot.get_user(user):
                user = _user
            else:
                user = discord.Object(user)
                user.name = _("[Unknown or Deleted User]")
        await ctx.send(
            _("Ok. I just unassigned {user.name} ({user.id}) from his personal role.").format(
                user=user
            )
        )

    @myrole.command(name="list")
    @commands.admin_or_permissions(manage_roles=True)
    async def mr_list(self, ctx):
        """Assigned roles list"""
        members_data = await self.config.all_members(ctx.guild)
        assigned_roles = []
        for member, data in members_data.items():
            if not data["role"]:
                continue
            dic = {
                _("User"): ctx.guild.get_member(member) or f"[X] {member}",
                _("Role"): shorten(
                    str(ctx.guild.get_role(data["role"]) or "[X] {}".format(data["role"])),
                    32,
                    placeholder="…",
                ),
            }
            assigned_roles.append(dic)
        pages = list(chat.pagify(tabulate(assigned_roles, headers="keys", tablefmt="orgtbl")))
        pages = [chat.box(page) for page in pages]
        if pages:
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            await ctx.send(chat.info(_("There is no assigned personal roles on this server")))

    @myrole.command(name="persistence")
    @commands.admin_or_permissions(manage_roles=True)
    async def mr_persistence(self, ctx):
        """Toggle auto-adding role on rejoin."""
        editing = self.config.guild(ctx.guild).role_persistence
        new_state = not await editing()
        await editing.set(new_state)
        await ctx.send(
            chat.info(
                _("Users will {}get their roles on rejoin now.").format(
                    "" if new_state else _("not ")
                )
            )
        )

    @myrole.group(name="blocklist", aliases=["blacklist"])
    @commands.admin_or_permissions(manage_roles=True)
    async def blacklist(self, ctx):
        """Manage blocklisted names"""
        pass

    @blacklist.command()
    async def add(self, ctx, *, rolename: str):
        """Add rolename to blocklist
        Members will be not able to change name of role to blocklisted names"""
        rolename = rolename.casefold()
        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            if rolename in blacklist:
                await ctx.send(chat.error(_("`{}` is already in blocklist").format(rolename)))
            else:
                blacklist.append(rolename)
                await ctx.send(
                    chat.info(_("Added `{}` to blocklisted roles list").format(rolename))
                )

    @blacklist.command()
    async def remove(self, ctx, *, rolename: str):
        """Remove rolename from blocklist"""
        rolename = rolename.casefold()
        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            if rolename not in blacklist:
                await ctx.send(chat.error(_("`{}` is not blocklisted").format(rolename)))
            else:
                blacklist.remove(rolename)
                await ctx.send(
                    chat.info(_("Removed `{}` from blocklisted roles list").format(rolename))
                )

    @blacklist.command(name="list")
    @commands.admin_or_permissions(manage_roles=True)
    async def bl_list(self, ctx):
        """List of blocklisted role names"""
        blacklist = await self.config.guild(ctx.guild).blacklist()
        pages = [chat.box(page) for page in chat.pagify("\n".join(blacklist))]
        if pages:
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            await ctx.send(chat.info(_("There is no blocklisted roles")))

    @commands.cooldown(1, 30, commands.BucketType.member)
    @myrole.command(aliases=["color"])
    @commands.check(has_assigned_role)
    @commands.bot_has_permissions(manage_roles=True)
    async def colour(self, ctx, *, colour: discord.Colour = discord.Colour.default()):
        """Change color of personal role"""
        role = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role)
        try:
            await role.edit(colour=colour, reason=get_audit_reason(ctx.author, _("Personal Role")))
        except discord.Forbidden:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(
                chat.error(_("Unable to edit role.\nRole must be lower than my top role"))
            )
        except discord.HTTPException as e:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(chat.error(_("Unable to edit role: {}").format(e)))
        else:
            if not colour.value:
                await ctx.send(
                    _("Reset {user}'s personal role color").format(user=ctx.message.author.name)
                )
            else:
                await ctx.send(
                    _("Changed color of {user}'s personal role to {color}").format(
                        user=ctx.message.author.name, color=colour
                    )
                )

    @commands.cooldown(1, 30, commands.BucketType.member)
    @myrole.command()
    @commands.check(has_assigned_role)
    @commands.bot_has_permissions(manage_roles=True)
    async def name(self, ctx, *, name: str):
        """Change name of personal role
        You cant use blocklisted names"""
        role = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role)
        name = name[:100]
        if name.casefold() in await self.config.guild(ctx.guild).blacklist():
            await ctx.send(chat.error(_("NONONO!!! This rolename is blocklisted.")))
            return
        try:
            await role.edit(name=name, reason=get_audit_reason(ctx.author, _("Personal Role")))
        except discord.Forbidden:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(
                chat.error(_("Unable to edit role.\nRole must be lower than my top role"))
            )
        except discord.HTTPException as e:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(chat.error(_("Unable to edit role: {}").format(e)))
        else:
            await ctx.send(
                _("Changed name of {user}'s personal role to {name}").format(
                    user=ctx.message.author.name, name=name
                )
            )

    @myrole.group(invoke_without_command=True)
    @commands.check(has_assigned_role)
    @commands.check(role_icons_feature)
    @commands.bot_has_permissions(manage_roles=True)
    async def icon(self, ctx):
        """Change icon of personal role"""
        pass

    @icon.command(name="emoji")
    async def icon_emoji(self, ctx, *, emoji: Union[discord.Emoji, discord.PartialEmoji] = None):
        """Change icon of personal role using emoji"""
        role = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role)
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
        try:
            if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
                await edit_role_icon(
                    self.bot,
                    role,
                    icon=await emoji.url_as(format="png").read(),
                    reason=get_audit_reason(ctx.author, _("Personal Role")),
                )
            else:
                await edit_role_icon(
                    self.bot,
                    role,
                    unicode_emoji=emoji,
                    reason=get_audit_reason(ctx.author, _("Personal Role")),
                )
        except discord.Forbidden:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(
                chat.error(_("Unable to edit role.\nRole must be lower than my top role"))
            )
        except discord.InvalidArgument:
            await ctx.send(chat.error(_("This image type is unsupported, or link is incorrect")))
        except discord.HTTPException as e:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(chat.error(_("Unable to edit role: {}").format(e)))
        else:
            await ctx.send(
                _("Changed icon of {user}'s personal role").format(user=ctx.message.author.name)
            )

    @icon.command(name="image", aliases=["url"])
    async def icon_image(self, ctx, *, url: str = None):
        """Change icon of personal role using image"""
        role = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role)
        if not (ctx.message.attachments or url):
            raise commands.BadArgument
        if ctx.message.attachments:
            image = await ctx.message.attachments[0].read()
        else:
            try:
                async with ctx.cog.session.get(url, raise_for_status=True) as resp:
                    image = await resp.read()
            except aiohttp.ClientResponseError as e:
                await ctx.send(chat.error(_("Unable to get image: {}").format(e.message)))
                return
        try:
            await edit_role_icon(
                self.bot,
                role,
                icon=image,
                reason=get_audit_reason(ctx.author, _("Personal Role")),
            )
        except discord.Forbidden:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(
                chat.error(_("Unable to edit role.\nRole must be lower than my top role"))
            )
        except discord.InvalidArgument:
            await ctx.send(chat.error(_("This image type is unsupported, or link is incorrect")))
        except discord.HTTPException as e:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(chat.error(_("Unable to edit role: {}").format(e)))
        else:
            await ctx.send(
                _("Changed icon of {user}'s personal role").format(user=ctx.message.author.name)
            )

    @icon.command(name="reset", aliases=["remove"])
    async def icon_reset(self, ctx):
        """Remove icon of personal role"""
        role = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role)
        try:
            await edit_role_icon(
                self.bot,
                role,
                icon=None,
                unicode_emoji=None,
                reason=get_audit_reason(ctx.author, _("Personal Role")),
            )
            await ctx.send(
                _("Removed icon of {user}'s personal role").format(user=ctx.message.author.name)
            )
        except discord.Forbidden:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(
                chat.error(_("Unable to edit role.\nRole must be lower than my top role"))
            )
        except discord.HTTPException as e:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(chat.error(_("Unable to edit role: {}").format(e)))

    @commands.Cog.listener("on_member_join")
    async def role_persistence(self, member):
        """Automatically give already assigned roles on join"""
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        if not await self.config.guild(member.guild).role_persistence():
            return
        await set_contextual_locales_from_guild(self.bot, member.guild)
        role = await self.config.member(member).role()
        if role:
            role = member.guild.get_role(role)
        if role and member:
            try:
                await member.add_roles(role, reason=_("Personal Role"))
            except discord.Forbidden:
                pass
