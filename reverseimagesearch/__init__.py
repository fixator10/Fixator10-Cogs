from .reverseimagesearch import ReverseImageSearch


def setup(bot):
    bot.add_cog(ReverseImageSearch(bot))
