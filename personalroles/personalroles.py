from asyncio import TimeoutError as AsyncTimeoutError
from textwrap import shorten
from typing import Dict, List, Literal, Optional, Union

import aiohttp
import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.mod import get_audit_reason
from redbot.core.utils.predicates import ReactionPredicate
from tabulate import tabulate

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

_ = Translator("PersonalRoles", __file__)


def has_assigned_role():
    async def _predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            return False
        role_id = await ctx.cog.config.member(ctx.author).role()
        role = ctx.guild.get_role(role_id)
        return role is not None

    return commands.check(_predicate)


def role_icons_feature():
    async def _predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            return False
        return "ROLE_ICONS" in ctx.guild.features

    return commands.check(_predicate)


@cog_i18n(_)
class PersonalRoles(commands.Cog):
    """Assign and edit personal roles"""

    __version__ = "2.2.5"

    # noinspection PyMissingConstructor
    def __init__(self, bot: Red):
        self.bot: Red = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession(json_serialize=json.dumps)
        self.config: Config = Config.get_conf(self, identifier=0x3D86BBD3E2B744AE8AA8B5D986EB4DD8)
        default_member: Dict[str, Optional[int]] = {
            "role": None,
            "limit": None,
        }
        default_guild: Dict[str, Union[List[int], bool]] = {
            "blacklist": [],
            "role_persistence": True,
        }
        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)

        # Set cooldown for `[p]myrole icon` commands
        self._icon_cd = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        for cmd in self.icon.walk_commands():
            cmd._buckets = self._icon_cd

    async def cog_unload(self):
        await self.session.close()

    def format_help_for_context(self, ctx: commands.Context) -> str:  # Thanks Sinbad!
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\n**Version**: {self.__version__}"

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int):
        # Thanks Sinbad
        data = await self.config.all_members()
        async for guild_id, members in AsyncIter(data.items()):
            if user_id in members:
                await self.config.member_from_ids(guild_id, user_id).clear()

    @commands.group()
    @commands.guild_only()
    async def myrole(self, ctx: commands.Context):
        """Control of personal role"""
        pass

    @myrole.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def assign(self, ctx: commands.Context, user: discord.Member, *, role: discord.Role):
        """Assign personal role to someone"""
        await self.config.member(user).role.set(role.id)
        await ctx.send(
            _(
                "Ok. I just assigned {user.name} ({user.id}) to role {role.name} ({role.id})."
            ).format(user=user, role=role)
        )

    @myrole.command()
    @commands.admin_or_permissions(manage_roles=True)
    async def unassign(
        self, ctx: commands.Context, *, user: Union[discord.Member, discord.User, int]
    ):
        """Unassign personal role from someone"""
        if isinstance(user, discord.Member):
            await self.config.member(user).clear()
        elif isinstance(user, int):
            await self.config.member_from_ids(ctx.guild.id, user).clear()
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
    async def mr_list(self, ctx: commands.Context):
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
    async def mr_persistence(self, ctx: commands.Context):
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

    @myrole.command(name="limit")
    @commands.admin_or_permissions(manage_roles=True)
    async def mr_limit(
        self,
        ctx: commands.Context,
        user: discord.Member,
        amount: commands.Range[int, 1, 30] = None,
    ):
        """Give users permissions on how many users they can share their personal role with.

        Run this command without the `amount` argument to clear the limit config.
        """
        if amount is None:
            await self.config.member(user).limit.clear()
            await ctx.send(f"Cleared the limit config for {user.display_name}.")
            return
        await self.config.member(user).limit.set(int(amount))
        await ctx.send(
            f"{user.display_name} can now share their personal role with {int(amount)} friends."
        )

    @myrole.group(name="blocklist", aliases=["blacklist"])
    @commands.admin_or_permissions(manage_roles=True)
    async def blacklist(self, ctx: commands.Context):
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
    async def remove(self, ctx: commands.Context, *, rolename: str):
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
    async def bl_list(self, ctx: commands.Context):
        """List of blocklisted role names"""
        blacklist = await self.config.guild(ctx.guild).blacklist()
        pages = [chat.box(page) for page in chat.pagify("\n".join(blacklist))]
        if pages:
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            await ctx.send(chat.info(_("There is no blocklisted roles")))

    @has_assigned_role()
    @commands.cooldown(1, 30, commands.BucketType.member)
    @myrole.command(aliases=["color"])
    @commands.bot_has_permissions(manage_roles=True)
    async def colour(
        self, ctx: commands.Context, *, colour: discord.Colour = discord.Colour.default()
    ):
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

    @myrole.command()
    @has_assigned_role()
    @commands.cooldown(1, 30, commands.BucketType.member)
    @commands.bot_has_permissions(manage_roles=True)
    async def name(self, ctx: commands.Context, *, name: str):
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

    @has_assigned_role()
    @role_icons_feature()
    @myrole.group(invoke_without_command=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def icon(self, ctx: commands.Context):
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
                await role.edit(
                    display_icon=await emoji.read(),
                    reason=get_audit_reason(ctx.author, _("Personal Role")),
                )
            else:
                await role.edit(
                    display_icon=emoji,
                    reason=get_audit_reason(ctx.author, _("Personal Role")),
                )
        except discord.Forbidden:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(
                chat.error(_("Unable to edit role.\nRole must be lower than my top role"))
            )
        except ValueError:
            await ctx.send(chat.error(_("This image type is unsupported, or link is incorrect")))
        except discord.HTTPException as e:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(chat.error(_("Unable to edit role: {}").format(e)))
        else:
            await ctx.send(
                _("Changed icon of {user}'s personal role").format(user=ctx.message.author.name)
            )

    @icon.command(name="image", aliases=["url"])
    async def icon_image(self, ctx: commands.Context, *, url: str = None):
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
            await role.edit(
                display_icon=image, reason=get_audit_reason(ctx.author, _("Personal Role"))
            )
        except discord.Forbidden:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(
                chat.error(_("Unable to edit role.\nRole must be lower than my top role"))
            )
        except ValueError:
            await ctx.send(chat.error(_("This image type is unsupported, or link is incorrect")))
        except discord.HTTPException as e:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(chat.error(_("Unable to edit role: {}").format(e)))
        else:
            await ctx.send(
                _("Changed icon of {user}'s personal role").format(user=ctx.message.author.name)
            )

    @icon.command(name="reset", aliases=["remove"])
    async def icon_reset(self, ctx: commands.Context):
        """Remove icon of personal role"""
        role = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role)
        try:
            await role.edit(
                display_icon=None, reason=get_audit_reason(ctx.author, _("Personal Role"))
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

    @has_assigned_role()
    @myrole.command(aliases=["friend"])
    @commands.cooldown(1, 30, commands.BucketType.member)
    async def friends(
        self,
        ctx: commands.Context,
        add_or_remove: Literal["add", "remove"],
        user: Optional[discord.Member] = None,
    ):
        """
        Add or remove friends from your role.

        `<add_or_remove>` should be either `add` to add or `remove` to remove friends.
        """
        if user is None:
            await ctx.send("`User` is a required argument.")
            return

        role_id = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role_id)
        limit = await self.config.member(ctx.author).limit()

        if add_or_remove.lower() == "add" and limit is None:
            await ctx.send("You're not allowed to add you personal role to your friends.")
            ctx.command.reset_cooldown(ctx)
            return

        if add_or_remove.lower() == "add" and len(role.members) >= limit:
            await ctx.send(
                "You're at maximum capacity, you cannot add any more users to your role."
            )
            ctx.command.reset_cooldown(ctx)
            return

        added_or_not = discord.utils.get(user.roles, id=role.id)

        async with self.config.member(ctx.author).friends() as friends:
            if add_or_remove.lower() == "add":
                if added_or_not is None:
                    await ctx.send(f"{user.display_name} already has your personal role.")
                    return
                else:
                    try:
                        await user.add_roles(
                            role, reason=get_audit_reason(ctx.author, _("Personal Role"))
                        )
                    except discord.Forbidden:
                        ctx.command.reset_cooldown(ctx)
                        await ctx.send(
                            chat.error(
                                _("Unable to edit role.\nRole must be lower than my top role")
                            )
                        )
                    except discord.HTTPException as e:
                        ctx.command.reset_cooldown(ctx)
                        await ctx.send(chat.error(_("Unable to edit role: {}").format(e)))
            elif add_or_remove.lower() == "remove":
                if added_or_not:
                    await ctx.send(f"{user.display_name} does not have your personal role.")
                    return
                else:
                    try:
                        await user.remove_roles(
                            role, reason=get_audit_reason(ctx.author, _("Personal Role"))
                        )
                    except discord.Forbidden:
                        ctx.command.reset_cooldown(ctx)
                        await ctx.send(
                            chat.error(
                                _("Unable to edit role.\nRole must be lower than my top role")
                            )
                        )
                    except discord.HTTPException as e:
                        ctx.command.reset_cooldown(ctx)
                        await ctx.send(chat.error(_("Unable to edit role: {}").format(e)))
            else:
                await ctx.send("Not a valid `add_or_remove` option.")
                return

        await ctx.send(
            f"Successfully  {'added' if add_or_remove.lower() == 'add' else 'removed'} "
            f"your role {'to' if add_or_remove.lower() == 'add' else 'from'} {user.display_name}."
        )

    @commands.Cog.listener("on_member_join")
    async def role_persistence(self, member: discord.Member):
        """Automatically give already assigned roles on join"""
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        if not await self.bot.allowed_by_whitelist_blacklist(member):
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
