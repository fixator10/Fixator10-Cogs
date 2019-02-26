from .godvilledata import GodvilleData


def setup(bot):
    bot.add_cog(GodvilleData(bot))
