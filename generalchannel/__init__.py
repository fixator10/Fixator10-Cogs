from .generalchannel import GeneralChannel

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


async def setup(bot):
    cog = GeneralChannel(bot)
    await bot.add_cog(cog)
