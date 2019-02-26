from .datautils import DataUtils


def setup(bot):
    bot.add_cog(DataUtils(bot))
