from redbot.core import commands

from leveler.abc import CompositeMetaClass


class LevelSetBaseCMD(metaclass=CompositeMetaClass):
    @commands.group(name="lvlset")
    async def lvlset(self, ctx):
        """Profile configuration Options."""
        pass
