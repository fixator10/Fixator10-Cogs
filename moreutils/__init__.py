from .moreutils import MoreUtils


def setup(bot):
    bot.add_cog(MoreUtils(bot))
