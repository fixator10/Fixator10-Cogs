from .personalroles import PersonalRoles

__red_end_user_data_statement__ = (
    "This cog stores users data in form of «member : role» Discord IDs pairings.\n"
    "This cog supports data removal requests."
)


def setup(bot):
    bot.add_cog(PersonalRoles(bot))
