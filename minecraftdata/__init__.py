from .minecraftdata import MinecraftData


def setup(bot):
    bot.add_cog(MinecraftData(bot))
