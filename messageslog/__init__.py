from .messageslog import MessagesLog


async def setup(bot):
    cog = MessagesLog(bot)
    await cog.initialize()
    bot.add_cog(cog)
