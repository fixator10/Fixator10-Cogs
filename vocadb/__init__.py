from .vocadb import VocaDB

__red_end_user_data_statement__ = "This cog does not persistently store any PII data about users."


def setup(bot):
    bot.add_cog(VocaDB(bot))
