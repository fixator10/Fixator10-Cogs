from .massthings import MassThings


def setup(bot):
    bot.add_cog(MassThings(bot))
