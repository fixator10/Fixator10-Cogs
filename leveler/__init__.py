from .leveler import Leveler


async def setup(bot):
    cog = Leveler(bot)
    bot.add_cog(cog)
    await cog.initialize()
