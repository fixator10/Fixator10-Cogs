from redbot.core import commands

from leveler.abc import CompositeMetaClass


class LevelAdminBaseCMD(metaclass=CompositeMetaClass):
    @commands.admin_or_permissions(manage_guild=True)
    @commands.group()
    @commands.guild_only()
    async def lvladmin(self, ctx):
        """Admin options features."""
