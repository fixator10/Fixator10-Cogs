from .leveler import Leveler


async def setup(bot):
    n = Leveler(bot)
    bot.add_listener(n._handle_on_message, "on_message")
    bot.add_cog(n)
