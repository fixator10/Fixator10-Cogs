from .leveler import Leveler

__red_end_user_data_statement__ = (
    "This cog persistently stores next data about user:<br>"
    "&#32;• Discord user ID<br>"
    "&#32;•  Current username<br>"
    "&#32;•  Per-server XP data (current XP and current level)<br>"
    "&#32;•  Total count of XP on all servers<br>"
    "&#32;•  URLs to profile/rank/levelup backrounds<br>"
    "&#32;•  User-set title & info<br>"
    '&#32;•  User\'s "reputation" points count<br>'
    "&#32;•  Data about user's badges<br>"
    "&#32;•  Data about user's profile/rank/levelup colors<br>"
    "&#32;•  Timestamp of latest message and reputation<br>"
    "&#32;•  Last message text (for comparison)<br>"
    "This cog supports data removal requests."
)


async def setup(bot):
    cog = Leveler(bot)
    bot.add_cog(cog)
    await cog.initialize()
