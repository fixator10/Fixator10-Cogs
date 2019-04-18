from .messageslog import MessagesLog


def setup(bot):
    c = MessagesLog(bot)
    bot.add_listener(c.message_deleted, "on_message_delete")
    bot.add_listener(c.message_redacted, "on_message_edit")
    bot.add_cog(c)
