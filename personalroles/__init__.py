from redbot.core.bot import Red

from .personalroles import PersonalRoles

__red_end_user_data_statement__ = (
    "This cog stores users data in form of «member : role» Discord IDs pairings.\n"
    "This cog supports data removal requests."
)


async def setup(bot: Red):
    cog = PersonalRoles(bot)
    await bot.add_cog(cog)
