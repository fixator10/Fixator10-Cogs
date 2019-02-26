from .personalroles import PersonalRoles


def setup(bot):
    cog = PersonalRoles(bot)
    bot.add_listener(cog.role_persistance, "on_member_join")
    bot.add_cog(cog)
