import discord
import os
from tabulate import tabulate
from discord.ext import commands
from cogs.utils import checks
from cogs.utils import chat_formatting as chat
from cogs.utils.dataIO import dataIO


class SelfRole:
    """Let users assign roles without asking to mods"""

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.config_file = "data/selfrole/config.json"
        self.config = dataIO.load_json(self.config_file)

    @commands.group(pass_context=True, invoke_without_command=True)
    async def selfrole(self, ctx: commands.Context, *, role: discord.Role):
        """Assign yourself an role"""
        sv = ctx.message.server.id
        author = ctx.message.author
        if sv not in self.config:
            await self.bot.say(chat.error("Selfroles not configured for this server yet."))
            return
        if role.id in self.config[sv]:
            if role in author.roles:
                await self.bot.remove_roles(author, role)
                await self.bot.say(chat.info("Okay, removed your role `{}`".format(role)))
            else:
                await self.bot.add_roles(author, role)
                await self.bot.say(chat.info("Okay, added you role `{}`".format(role)))
        else:
            await self.bot.say(chat.error("This role is not allowed for selfrole. Check available roles with "
                                          "{}selfrole list".format(ctx.prefix) +
                                          chat.box("Username is not in sudoers file.\n"
                                                   "This incident will be reported.")))

    @selfrole.command(pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def add(self, ctx: commands.Context, *, role: discord.Role):
        """Add an role to accessible roles for selfrole command"""
        sv = ctx.message.server.id
        if sv not in self.config:
            self.config[sv] = []
        if role.id in self.config[sv]:
            await self.bot.say(chat.error("This role is already in selfrole list"))
        else:
            self.config[sv].append(role.id)
            dataIO.save_json(self.config_file, self.config)
            await self.bot.say(chat.info("Added role `{}` (`{}`) as available "
                                         "for selfrole command".format(role.name, role.id)))

    @selfrole.command(pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def remove(self, ctx: commands.Context, *, role: discord.Role):
        """Remove role to accessible roles for selfrole command"""
        sv = ctx.message.server.id
        if sv not in self.config:
            self.config[sv] = []
        if role.id not in self.config[sv]:
            await self.bot.say(chat.error("This role is not in selfrole list"))
        else:
            self.config[sv].remove(role.id)
            dataIO.save_json(self.config_file, self.config)
            await self.bot.say(chat.info("Removed role `{}` (`{}`) from list of available roles "
                                         "for selfrole command".format(role.name, role.id)))

    @selfrole.command(pass_context=True, hidden=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def removeid(self, ctx: commands.Context, *, id: str):
        """Remove role to accessible roles for selfrole command by id"""
        sv = ctx.message.server.id
        if sv not in self.config:
            self.config[sv] = []
        if id not in self.config[sv]:
            await self.bot.say(chat.error("This role is not in selfrole list"))
        else:
            self.config[sv].remove(id)
            dataIO.save_json(self.config_file, self.config)
            await self.bot.say(chat.info("Removed role with id `{}` from list of available roles "
                                         "for selfrole command".format(id)))

    @selfrole.command(pass_context=True)
    async def list(self, ctx: commands.Context):
        """Shows up an list of available roles for selfrole command"""
        sv = ctx.message.server.id
        roles = []
        if sv not in self.config:
            await self.bot.say("Not configured for this server.")
            return
        for roleid in self.config[sv]:
            role = discord.utils.get(ctx.message.server.roles, id=roleid)
            dic = {
                "Role": role is not None and role.name or roleid,
                "ID": roleid
            }
            roles.append(dic)
        for page in chat.pagify(tabulate(roles,
                                         headers="keys",
                                         tablefmt="orgtbl")):
            await self.bot.say(chat.box(page))


def check_folders():
    if not os.path.exists("data/selfrole"):
        os.makedirs("data/selfrole")


def check_files():
    system = {}
    f = "data/selfrole/config.json"
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, system)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(SelfRole(bot))
