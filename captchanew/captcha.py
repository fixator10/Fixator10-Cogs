import discord
from redbot.core import Config, commands
from redbot.core.bot import Red

from captchanew.api import CaptchaAPI

from .abc import CogABC, CogMixin
from .commands import Commands
from .meta import __patch_note_version__, __patchnote__
from .migration import run_migration
from .utils import get_config, get_log

log = get_log()


class Captcha(
    commands.Cog, CaptchaAPI, Commands, CogABC, metaclass=CogMixin
):  # Keep "CogABC" after all others classes (It has its importance)
    def __init__(self, bot: Red) -> None:
        self.bot = bot

        self.config = get_config(with_defaults=True)

    async def initiate_patch_note(self) -> None:
        await self.bot.wait_until_red_ready()
        if not self.bot.user:
            raise ValueError()

        notice = Config.get_conf(None, identifier=4145125452, cog_name="PredeactorNews")
        notice.register_user(version="0")

        async with notice.get_users_lock():
            await self.bot.wait_until_red_ready()
            actual_patch_note_version: str = await notice.user(self.bot.user).version()  # type: ignore

            if actual_patch_note_version != __patch_note_version__:

                # P.N. 2
                # Determine if this is the first time the user is using the cog (Not a change
                # of repo, see https://github.com/fixator10/Fixator10-Cogs/pull/163)
                if __patch_note_version__ == "2" and (not await self.config.was_loaded_once()):
                    await notice.user(self.bot.user).version.set(__patch_note_version__)  # type: ignore
                    return

                await self.bot.send_to_owners(__patchnote__)
                await notice.user(self.bot.user).version.set(__patch_note_version__)


def setup(bot: Red):
    cog = Captcha(bot)
    bot.add_cog(cog)
    bot.loop.create_task(run_migration())
    bot.loop.create_task(cog.initiate_patch_note())
