from abc import ABCMeta
from enum import Enum

from redbot.core import commands
from redbot.core.utils.chat_formatting import warning

from ..abc import MixinMeta


class OwnerCommands(MixinMeta, metaclass=ABCMeta):
    @commands.group(name="ownersetcaptcha", aliases=["setownercaptcha", "captchasetowner"])
    @commands.is_owner()
    async def ownercmd(self, ctx: commands.GuildContext):
        """
        Set options for the Captcha cog.
        """
        pass

    @ownercmd.command(name="setlog")
    async def logging_level_setter(self, ctx: commands.Context, logging_level: int):
        """
        Set the logging level of the cog.

        The logging level must be an integrer between 1 and 5.
        The lowest the logging level is, the more alert you will receive in your bot's log.

        1 - DEBUG
        2 - INFO
        3 - WARNING
        4 - ERROR
        5 - CRITICAL

        **Level 1 is meant for developers, tester and monitoring purpose.**
        """
        if logging_level > 5:
            await ctx.send("The logging level cannot be more than 5.")
            return
        if logging_level < 0:
            await ctx.send("The logging level cannot be less than 0.")
        value = getattr(LoggingLevels, "Lvl" + str(logging_level)).value
        await self.data.log_level.set(logging_level * 10)
        await ctx.send(
            warning(
                "The logging level has been set to: {val}, {lev}".format(
                    val=value, lev=logging_level
                )
            )
        )

        await self._initialize(False)


class LoggingLevels(Enum):
    Lvl5 = "CRITICAL"
    Lvl4 = "ERROR"
    Lvl3 = "WARNING"
    Lvl2 = "INFO"
    Lvl1 = "DEBUG"
    Lvl0 = "NOTSET"
