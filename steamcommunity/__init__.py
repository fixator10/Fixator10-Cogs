from .steamcommunity import SteamCommunity


async def setup(bot):
    cog = SteamCommunity(bot)
    await cog.initialize()
    bot.add_cog(cog)
