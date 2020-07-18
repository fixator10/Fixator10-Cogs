from asyncio import create_task

from .datautils import DataUtils


async def setup_after_ready(bot):
    await bot.wait_until_red_ready()
    cog = DataUtils(bot)
    for name, command in cog.all_commands.items():
        if bot.get_command(name):
            command.name = f"du{command.name}"
        for alias in command.aliases:
            if bot.get_command(alias):
                command.aliases[command.aliases.index(alias)] = f"du{alias}"
    bot.add_cog(cog)


def setup(bot):
    create_task(setup_after_ready(bot))
