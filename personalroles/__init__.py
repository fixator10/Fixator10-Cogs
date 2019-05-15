from .personalroles import PersonalRoles


def setup(bot):
    bot.add_cog(PersonalRoles(bot))
