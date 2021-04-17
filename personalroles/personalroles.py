from textwrap import shorten
from typing import Union

import discord
from redbot.core import checks, commands
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.mod import get_audit_reason
from tabulate import tabulate

_ = Translator("PersonalRoles", __file__)


async def has_assigned_role(ctx):
    return ctx.guild.get_role(await ctx.cog.config.member(ctx.author).role())


@cog_i18n(_)
class PersonalRoles(commands.Cog):
    """Assign and edit personal roles"""

    __version__ = "2.1.5"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0x3D86BBD3E2B744AE8AA8B5D986EB4DD8)
        default_member = {"role": None}
        default_guild = {"blacklist": [], "role_persistence": True}
        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)

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
    @checks.admin_or_permissions(manage_roles=True)
    async def assign(self, ctx, user: discord.Member, *, role: discord.Role):
        """Assign personal role to someone"""
        await self.config.member(user).role.set(role.id)
        await ctx.send(
            _(
                "Ok. I just assigned {user.name} ({user.id}) to role {role.name} ({role.id})."
            ).format(user=user, role=role)
        )

    @myrole.command()
    @checks.admin_or_permissions(manage_roles=True)
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
    @checks.admin_or_permissions(manage_roles=True)
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
    @checks.admin_or_permissions(manage_roles=True)
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
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
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
    @checks.admin_or_permissions(manage_roles=True)
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
    @commands.guild_only()
    @commands.check(has_assigned_role)
    async def colour(self, ctx, *, colour: discord.Colour = discord.Colour.default()):
        """Change color of personal role"""
        role = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role)
        try:
            await role.edit(colour=colour, reason=get_audit_reason(ctx.author, _("Personal Role")))
        except discord.Forbidden:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(
                chat.error(
                    _(
                        "Unable to edit role.\n"
                        'Role must be lower than my top role and i must have permission "Manage Roles"'
                    )
                )
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
    @commands.guild_only()
    @commands.check(has_assigned_role)
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
                chat.error(
                    _(
                        "Unable to edit role.\n"
                        'Role must be lower than my top role and i must have permission "Manage Roles"'
                    )
                )
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
