from .godvilledata import GodvilleData

__red_end_user_data_statement__ = (
    "This cog stores https://godville.net API-tokens if provided by user.\n"
    "Users may delete their tokens by either via `[p]godville apikey remove` or via data removal request."
)


async def setup(bot):
    await bot.add_cog(GodvilleData(bot))
