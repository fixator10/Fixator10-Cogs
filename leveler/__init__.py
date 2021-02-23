from warnings import filterwarnings

filterwarnings("ignore", category=DeprecationWarning, module=r"fontTools.")
from .leveler import Leveler

__red_end_user_data_statement__ = (
    "This cog persistently stores next data about user:<br>"
    "•    Discord user ID<br>"
    "•    Current username<br>"
    "•    Per-server XP data (current XP and current level)<br>"
    "•    Total count of XP on all servers<br>"
    "•    URLs to profile/rank/levelup backrounds<br>"
    "•    User-set title & info<br>"
    '•    User\'s "reputation" points count<br>'
    "•    Data about user's badges<br>"
    "•    Data about user's profile/rank/levelup colors<br>"
    "•    Timestamp of latest message and reputation<br>"
    "•    Last message text (for comparison)<br>"
    "This cog supports data removal requests."
)


async def setup(bot):
    cog = Leveler(bot)
    bot.add_cog(cog)
    bot.loop.create_task(cog.initialize())
