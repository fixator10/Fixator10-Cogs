from pathlib import Path

import discord
from redbot.core import checks
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.data_converter import DataConverter as dc
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core.utils.mod import get_audit_reason
from tabulate import tabulate


def has_assigned_role(ctx):
    return ctx.cog.config.member(ctx.author).role()


class PersonalRoles(commands.Cog):
    """Assign and edit personal roles"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0x3d86bbd3e2b744ae8aa8b5d986eb4dd8)
        default_member = {"role": None}
        default_guild = {"blacklist": []}
        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)

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
        await ctx.send("Ok. I just assigned {} ({}) to role {} ({})."
                       .format(user.name, user.id, role.name, role.id))

    @myrole.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def unassign(self, ctx, *, user: discord.Member):
        """Unassign personal role from someone"""
        await self.config.member(user).role.clear()
        await ctx.send("Ok. I just unassigned {} ({}) from his personal role.".format(user.name, user.id))

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
                "User": ctx.guild.get_member(member) or f"[X] {await self.bot.get_user_info(member)}",
                "Role": await self.smart_truncate(ctx.guild.get_role(data["role"] or "[X] {}".format(data["role"])))
            }
            assigned_roles.append(dic)
        pages = list(chat.pagify(tabulate(assigned_roles, headers="keys", tablefmt="orgtbl")))
        pages = [chat.box(page) for page in pages]
        await menu(ctx, pages, DEFAULT_CONTROLS)

    @myrole.command()
    @checks.is_owner()
    async def convertv2(self, ctx, path):
        """Convert data from V2 cog"""
        base_path = Path(path)
        fp = base_path / 'data' / 'personalroles' / 'config.json'
        if not fp.is_file():
            ctx.send(chat.error("Config is not found, check your path and try again"))
            return
        converter = dc(self.config)

        def conversion_spec(v2data: dict):
            for server in v2data.keys():
                yield {(Config.GUILD, server): {("blacklist",): v2data[server]["blacklist"]}}
                for user in v2data[server]["users"]:
                    yield {(Config.MEMBER, server, user): {("role",): int(v2data[server]["users"][user])}}

        await converter.convert(fp, conversion_spec)
        await ctx.tick()

    @myrole.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def blacklist(self, ctx):
        """Manage blacklisted names"""
        pass

    @blacklist.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def add(self, ctx, *, rolename: str):
        """Add rolename to blacklist
        Members will be not able to change name of role to blacklisted names"""
        rolename = rolename.casefold()
        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            if rolename in blacklist:
                await ctx.send(chat.error("`{}` is already in blacklist".format(rolename)))
            else:
                blacklist.append(rolename)
                await ctx.send(chat.info("Added `{}` to blacklisted roles list".format(rolename)))

    @blacklist.command()
    @checks.admin_or_permissions(manage_roles=True)
    async def remove(self, ctx, *, rolename: str):
        """Remove rolename from blacklist"""
        rolename = rolename.casefold()
        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            if rolename not in blacklist:
                await ctx.send(chat.error("`{}` is not blacklisted".format(rolename)))
            else:
                blacklist.remove(rolename)
                await ctx.send(chat.info("Removed `{}` from blacklisted roles list".format(rolename)))

    @blacklist.command(name="list")
    @checks.admin_or_permissions(manage_roles=True)
    async def bl_list(self, ctx):
        """List of blacklisted role names"""
        blacklist = await self.config.guild(ctx.guild).blacklist()
        pages = [chat.box(page) for page in chat.pagify('\n'.join(blacklist))]
        if pages:
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            await ctx.send(chat.info("There is no blacklisted roles"))

    @commands.cooldown(1, 30, commands.BucketType.user)
    @myrole.command(aliases=["color"])
    @commands.guild_only()
    @commands.check(has_assigned_role)
    async def colour(self, ctx, *, colour: discord.Colour = discord.Colour.default()):
        """Change color of personal role"""
        role = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role)
        try:
            await role.edit(colour=colour, reason=get_audit_reason(ctx.author, "Personal Role"))
        except discord.Forbidden:
            await ctx.send(chat.error("Unable to edit role.\nRole must be lower than my top role and i must have "
                                      "permission \"Manage Roles\""))
        else:
            await ctx.send("Changed color of {}'s personal role to {}".format(ctx.message.author.name, colour))

    @commands.cooldown(1, 30, commands.BucketType.user)
    @myrole.command()
    @commands.guild_only()
    @commands.check(has_assigned_role)
    async def name(self, ctx, *, name: str):
        """Change name of personal role
        You cant use blacklisted names or control role names"""
        role = await self.config.member(ctx.author).role()
        role = ctx.guild.get_role(role)
        name = name[:100]
        if name.casefold() in await self.config.guild(ctx.guild).blacklist():
            await ctx.send(chat.error("NONONO!!! This rolename is blacklisted."))
            return
        try:
            await role.edit(name=name, reason=get_audit_reason(ctx.author, "Personal Role"))
        except discord.Forbidden:
            await ctx.send(chat.error("Unable to edit role.\nRole must be lower than my top role and i must have "
                                      "permission \"Manage Roles\""))
        else:
            await ctx.send("Changed name of {}'s personal role to {}".format(ctx.message.author.name, name))

    async def smart_truncate(self, content, length=32, suffix='…'):
        """https://stackoverflow.com/questions/250357/truncate-a-string-without-ending-in-the-middle-of-a-word"""
        content_str = str(content)
        if len(content_str) <= length:
            return content
        return ' '.join(content_str[:length + 1].split(' ')[0:-1]) + suffix

    async def role_persistance(self, member):
        """Automatically give already assigned roles on join"""
        role = await self.config.member(member).role()
        if role:
            role = member.guild.get_role(role)
            if role and member:
                try:
                    await member.add_roles(role, reason="Personal Role")
                except discord.Forbidden:
                    pass
