from .messageslog import MessagesLog

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


async def setup(bot):
    cog = MessagesLog(bot)
    await cog.initialize()
    await bot.add_cog(cog)
