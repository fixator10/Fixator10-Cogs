from .adminutils import AdminUtils


def setup(bot):
    bot.add_cog(AdminUtils(bot))
