from asyncio import create_task

from .adminutils import AdminUtils


async def setup_after_ready(bot):
    await bot.wait_until_red_ready()
    cog = AdminUtils(bot)
    for name, command in cog.all_commands.items():
        if bot.get_command(name):
            command.name = f"a{command.name}"
        for alias in command.aliases:
            if bot.get_command(alias):
                command.aliases[command.aliases.index(alias)] = f"a{alias}"
    bot.add_cog(cog)


def setup(bot):
    create_task(setup_after_ready(bot))
