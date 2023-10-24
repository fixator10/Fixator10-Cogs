from asyncio import create_task

from .moreutils import MoreUtils

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


async def setup_after_ready(bot):
    await bot.wait_until_red_ready()
    cog = MoreUtils(bot)
    for name, command in cog.all_commands.items():
        if not command.parent:
            if bot.get_command(name):
                command.name = f"mu{command.name}"
            for alias in command.aliases:
                if bot.get_command(alias):
                    command.aliases[command.aliases.index(alias)] = f"mu{alias}"
    await bot.add_cog(cog)


async def setup(bot):
    create_task(setup_after_ready(bot))
