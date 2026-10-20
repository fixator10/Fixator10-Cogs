from .massthings import MassThings

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
    # "<s>If you are using this cog, user data storage will probably be much less significant thing then API abuse</s>"
)


async def setup(bot):
    await bot.add_cog(MassThings(bot))
