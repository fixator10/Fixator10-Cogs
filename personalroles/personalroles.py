import os

import discord
from __main__ import settings
from discord.ext import commands
from tabulate import tabulate

from cogs.utils import chat_formatting as chat
from cogs.utils import checks
from cogs.utils.dataIO import dataIO


class PRCustomCheck:
    # noinspection PyMethodParameters
    def assigned_role():
        def predicate(ctx: commands.Context):
            config_file = "data/personalroles/config.json"
            config = dataIO.load_json(config_file)
            author = ctx.message.author
            server = ctx.message.server
            if author.id in config[server.id]["users"]:
                return True
            else:
                return False

        return commands.check(predicate)


class PersonalRoles:
    """Assign and edit personal roles"""

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.config_file = "data/personalroles/config.json"
        self.config = dataIO.load_json(self.config_file)

    @commands.group(pass_context=True, no_pm=True)
    async def myrole(self, ctx):
        """Control of personal role"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @myrole.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def assign(self, ctx, user: discord.Member, *, role: discord.Role):
        """Assign personal role to someone"""
        sv = ctx.message.server.id
        if sv not in self.config:
            self.config[sv] = {"users": {}, "blacklist": []}
        self.config[sv]["users"][user.id] = role.id
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say("Ok. I just assigned {} ({}) to role {} ({})."
                           .format(user.name, user.id, role.name, role.id))

    @myrole.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def unassign(self, ctx, *, user: discord.Member):
        """Unassign personal role from someone"""
        sv = ctx.message.server.id
        if sv not in self.config or user.id not in self.config[sv]["users"]:
            await self.bot.say("Can't find {} ({}) in assigned roles list.".format(user.name, user.id))
            return
        del self.config[sv]["users"][user.id]
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say("Ok. I just unassigned {} ({}) from his personal role.".format(user.name, user.id))

    @myrole.command(pass_context=True, no_pm=True, hidden=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def unassignid(self, ctx, *, id: str):
        """Unassign personal role from someone by ID"""
        sv = ctx.message.server.id
        if sv not in self.config or id not in self.config[sv]["users"]:
            await self.bot.say("Can't find {} in assigned roles list.".format(id))
            return
        del self.config[sv]["users"][id]
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say("Ok. I just removed {} from assigned roles list.".format(id))

    @myrole.command(pass_context=True, no_pm=True, name="list")
    @checks.admin_or_permissions(manage_roles=True)
    async def mr_list(self, ctx):
        """Assigned roles list"""
        sv = ctx.message.server.id
        assigned_roles = []
        if sv not in self.config:
            await self.bot.say("Not configured for this server.")
            return
        for key, value in self.config[sv]["users"].items():
            dic = {
                "User": discord.utils.get(ctx.message.server.members, id=key) or key,
                "Role": discord.utils.get(ctx.message.server.roles, id=value) or value
            }
            assigned_roles.append(dic)
        for page in chat.pagify(tabulate(assigned_roles,
                                         headers="keys",
                                         tablefmt="orgtbl")):
            await self.bot.say(chat.box(page))

    @myrole.group(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def blacklist(self, ctx):
        """Manage blacklisted names"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @blacklist.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def add(self, ctx, rolename: str):
        """Add rolename to blacklist
        Members will be not able to change name of role to blacklisted names"""
        rolename = rolename.casefold()
        sv = ctx.message.server.id
        if sv not in self.config:
            self.config[sv] = {"users": {}, "blacklist": []}
        if rolename in self.config[sv]["blacklist"]:
            await self.bot.say(chat.error("`{}` is already in blacklist".format(rolename)))
        else:
            self.config[sv]["blacklist"].append(rolename)
            dataIO.save_json(self.config_file, self.config)
            await self.bot.say(chat.info("Added `{}` to blacklisted roles list".format(rolename)))

    @blacklist.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def remove(self, ctx, rolename: str):
        """Remove rolename from blacklist"""
        rolename = rolename.casefold()
        sv = ctx.message.server.id
        if sv not in self.config or rolename not in self.config[sv]["blacklist"]:
            await self.bot.say(chat.error("`{}` is not blacklisted".format(rolename)))
        else:
            self.config[sv]["blacklist"].remove(rolename)
            dataIO.save_json(self.config_file, self.config)
            await self.bot.say(chat.info("Removed `{}` from blacklisted roles list".format(rolename)))

    @blacklist.command(pass_context=True, no_pm=True, name="list")
    @checks.admin_or_permissions(manage_roles=True)
    async def bl_list(self, ctx):
        """List of blacklisted roles"""
        sv = ctx.message.server.id
        if sv not in self.config:
            await self.bot.say("Not configured for this server.")
            return
        rolenames = self.config[sv]["blacklist"]
        await self.bot.say(chat.box('\n'.join(str(p) for p in rolenames)))

    @commands.cooldown(1, 30, commands.BucketType.user)
    @myrole.command(pass_context=True, aliases=["color"], no_pm=True)
    @PRCustomCheck.assigned_role()
    async def colour(self, ctx, *, colour: discord.Colour):
        """Change color of personal role"""
        sv = ctx.message.server.id
        authorid = ctx.message.author.id
        if sv not in self.config or authorid not in self.config[sv]["users"]:
            await self.bot.say("Looks like you are not in server's roles list."
                               " Contact admin/mod for assign your personal role to you.")
        else:
            await self.bot.edit_role(ctx.message.server,
                                     discord.utils.get(ctx.message.server.roles, id=self.config[sv]["users"][authorid]),
                                     colour=colour)
            await self.bot.say("Changed color of {}'s personal role to {}".format(ctx.message.author.name, colour))

    @commands.cooldown(1, 30, commands.BucketType.user)
    @myrole.command(pass_context=True, no_pm=True)
    @PRCustomCheck.assigned_role()
    async def name(self, ctx, *, name: str):
        """Change name of personal role
        You cant use blacklisted names or control role names"""
        sv = ctx.message.server.id
        authorid = ctx.message.author.id
        if sv not in self.config or authorid not in self.config[sv]["users"]:
            await self.bot.say("Looks like you are not in server's roles list."
                               " Contact admin/mod for assign your personal role to you.")
        if len(name) > 100:
            name = name[:100]
        else:
            if name.casefold() in self.config[sv]["blacklist"] \
                    or settings.get_server_mod(ctx.message.server).lower() == name.lower() \
                    or settings.get_server_admin(ctx.message.server).lower() == name.lower():
                await self.bot.say(chat.error("NONONO!!! This rolename is blacklisted."))
                return
            await self.bot.edit_role(ctx.message.server,
                                     discord.utils.get(ctx.message.server.roles, id=self.config[sv]["users"][authorid]),
                                     name=name)
            await self.bot.say("Changed name of {}'s personal role to {}".format(ctx.message.author.name, name))


def check_folders():
    if not os.path.exists("data/personalroles"):
        os.makedirs("data/personalroles")


def check_files():
    system = {}
    f = "data/personalroles/config.json"
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, system)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(PersonalRoles(bot))
