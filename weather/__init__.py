from .weather import Weather

__red_end_user_data_statement__ = (
    "This cog may store data about user's preferred measuring units.\n"
    "This data can be remove by either via `[p]forecastunits reset` or via data removal request."
)


async def setup(bot):
    await bot.add_cog(Weather(bot))
