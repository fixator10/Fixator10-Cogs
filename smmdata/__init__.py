from .smmdata import SMMData


def setup(bot):
    bot.add_cog(SMMData(bot))
