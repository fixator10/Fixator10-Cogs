from .messageslog import MessagesLog


def setup(bot):
    bot.add_cog(MessagesLog(bot))
