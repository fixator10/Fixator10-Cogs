from .translators import Translators


def setup(bot):
    bot.add_cog(Translators(bot))
