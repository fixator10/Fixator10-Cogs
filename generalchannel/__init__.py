from .generalchannel import GeneralChannel


def setup(bot):
    bot.add_cog(GeneralChannel(bot))
