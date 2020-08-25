from leveler.abc import CompositeMetaClass
from redbot.core import commands


class DBConvertersBaseCMD(metaclass=CompositeMetaClass):
    @commands.group()
    @commands.is_owner()
    async def lvlconvert(self, ctx):
        """Convert levels from other leveling systems."""
