from .leveler import Leveler


async def setup(bot):
    bot.add_cog(Leveler(bot))
