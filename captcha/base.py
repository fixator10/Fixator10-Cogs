import logging
from contextlib import suppress
from datetime import datetime
from typing import Optional, Union

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.commands import MissingPermissions
from redbot.core.utils.chat_formatting import bold, error, humanize_list

from .abc import CompositeMetaClass
from .api import Challenge
from .commands import OwnerCommands, Settings
from .errors import (
    AlreadyHaveCaptchaError,
    AskedForReload,
    DeletedValueError,
    LeftServerError,
    MissingRequiredValueError,
)
from .events import Listeners
from .informations import __author__, __patchnote__, __patchnote_version__, __version__
from .utils import build_kick_embed

DEFAULT_GLOBAL = {
    "log_level": 50,
    "was_loaded_once": False,  # If this is the first time we load the cog. The value isn't really interesting
}
DEFAULT_GUILD = {
    "channel": None,  # The channel where the captcha is sent.
    "logschannel": None,  # Where logs are sent.
    "enabled": False,  # If challenges must be activated.
    "autoroles": [],  # Roles to give.
    "temprole": None,  # Temporary role to give.
    "type": "plain",  # Captcha type.
    "timeout": 5,  # Time in minutes before kicking.
    "retry": 3,  # The number of retry allowed.
}
log = logging.getLogger("red.fixator10-cogs.captcha")


class Captcha(
    Settings,
    OwnerCommands,
    Listeners,
    commands.Cog,
    name="Captcha",
    metaclass=CompositeMetaClass,
):
    """A Captcha defensive system. to challenge the new users and protect yourself a bit more of
    raids."""

    __author__ = __author__
    __version__ = __version__

    def __init__(self, bot: Red) -> None:
        super().__init__()

        self.bot: Red = bot

        self.data: Config = Config.get_conf(None, identifier=495954056, cog_name="Captcha")
        self.data.register_global(**DEFAULT_GLOBAL)
        self.data.register_guild(**DEFAULT_GUILD)

        self.running = {}

        self.patchnote = __patchnote__
        self.patchnoteconfig = None

    async def send_or_update_log_message(
        self,
        guild: discord.Guild,
        message_content: str,
        message_to_update: Optional[discord.Message] = None,
        *,
        allowed_tries: tuple = None,
        member: discord.Member = None,
        file: discord.File = None,
        embed: discord.Embed = None,
        ignore_error: bool = True,
    ) -> Optional[discord.Message]:
        """
        Send a message or update one in the log channel.
        """
        time = datetime.now().strftime("%H:%M - %m/%d/%Y")
        content = ""
        if message_to_update:
            content += message_to_update.content + "\n"
        content += (
            f"{bold(str(time))}{f' {member.mention}' if member else ''}"
            f"{f' ({allowed_tries[0]}/{allowed_tries[1]})' if allowed_tries else ''}: "
            f"{message_content}"
        )

        log_channel_id: Union[int, None] = await self.data.guild(guild).logschannel()
        if not log_channel_id:
            if ignore_error:
                return None
            raise MissingRequiredValueError("Missing logging channel ID.")

        log_channel: discord.TextChannel = self.bot.get_channel(log_channel_id)
        if log_channel and message_to_update:
            try:
                await message_to_update.edit(
                    content=content,
                    file=file,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(users=False),
                )
            except discord.HTTPException:
                if message_to_update.embeds and (
                    message_to_update.embeds[0].title == "Message reached his maximum capacity!"
                ):
                    # To avoid edit spam or something... smh
                    return message_to_update
                await message_to_update.edit(
                    content=message_to_update.content,
                    file=file,
                    embed=discord.Embed(
                        colour=discord.Colour.red().value,
                        title="Message reached his maximum capacity!",
                        description=(
                            "I am unable to log more since the characters limit on this "
                            "message has been reached."
                        ),
                    ),
                    allowed_mentions=discord.AllowedMentions(users=False),
                )
            return message_to_update
        if log_channel:
            return await log_channel.send(
                content,
                file=file,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        raise DeletedValueError("Logging channel may have been deleted.")

    async def basic_check(self, member: discord.Member) -> bool:
        """
        Check the basis from a member; used when a member join the server.
        """
        return False if member.bot else await self.data.guild(member.guild).enabled()

    async def create_challenge_for(self, member: discord.Member) -> Challenge:
        """
        Create a Challenge class for a user and append it to the running challenges.
        """
        if member.id in self.running:
            raise AlreadyHaveCaptchaError("The user already have a captcha object running.")
        config = await self.data.guild(member.guild).all()
        channel = config["channel"]
        if not channel:
            raise MissingRequiredValueError("Missing channel for verification.")
        if channel == "dm":
            channel = member.dm_channel or await member.create_dm()
        else:
            channel = self.bot.get_channel(channel)
        captcha = Challenge(self.bot, member, channel, config)
        self.running[member.id] = captcha
        return captcha

    async def delete_challenge_for(self, member: discord.Member) -> bool:
        try:
            del self.running[member.id]
            return True
        except KeyError:
            return False

    def is_running_challenge(self, member_or_id: Union[discord.Member, int]) -> bool:
        if isinstance(member_or_id, discord.Member):
            member_or_id = int(member_or_id.id)
        return member_or_id in self.running

    def obtain_challenge(self, member_or_id: Union[discord.Member, int]) -> Challenge:
        if isinstance(member_or_id, discord.Member):
            member_or_id = int(member_or_id.id)
        if not self.is_running_challenge(member_or_id):
            raise KeyError("User is not challenging any Captcha.")
        return self.running[member_or_id]

    async def give_temprole(self, challenge: Challenge) -> None:
        if temprole := challenge.config["temprole"]:
            try:
                await challenge.member.add_roles(
                    challenge.guild.get_role(temprole), reason="Beginning Captcha challenge."
                )
            except discord.Forbidden:
                raise MissingPermissions('Bot miss the "manage_roles" permission.')

    async def remove_temprole(self, challenge: Challenge) -> None:
        if temprole := challenge.config["temprole"]:
            try:
                await challenge.member.remove_roles(
                    challenge.guild.get_role(temprole), reason="Finishing Captcha challenge."
                )
            except discord.Forbidden:
                raise MissingPermissions('Bot miss the "manage_roles" permission.')

    async def realize_challenge(self, challenge: Challenge) -> None:
        # Seems to be the last goddamn function I'll be writing...
        limit = await self.data.guild(challenge.member.guild).retry()
        is_ok = None
        timeout = False
        await self.give_temprole(challenge)
        try:
            while is_ok is not True and (not challenge.trynum > limit):
                try:
                    this = await challenge.try_challenging()
                except TimeoutError:
                    timeout = True
                    break
                except AskedForReload:
                    challenge.trynum += 1
                    continue
                except LeftServerError:
                    return False
                except TypeError:
                    # In this error, the user reacted with an invalid (Most probably custom)
                    # emoji. While I expect administrator to remove this permissions, I still
                    # need to handle, so we're fine if we don't increase trynum.
                    continue
                if this is False:
                    challenge.trynum += 1
                    try:
                        await challenge.messages["answer"].delete()
                    except discord.Forbidden:
                        await self.send_or_update_log_message(
                            challenge.guild,
                            error(bold("Unable to delete member's answer.")),
                            challenge.messages.get("logs"),
                            member=challenge.member,
                        )
                    is_ok = False
                else:
                    is_ok = True

            failed = challenge.trynum > limit
            logmsg = challenge.messages["logs"]

            if failed or timeout:
                reason = (
                    "Retried the captcha too many time."
                    if failed
                    else "Didn't answer to the challenge."
                )
                try:
                    await self.nicely_kick_user_from_challenge(challenge, reason)
                    await self.send_or_update_log_message(
                        challenge.guild,
                        bold(f"User kicked for reason: {reason}"),
                        logmsg,
                        member=challenge.member,
                    )
                except MissingPermissions:
                    await self.send_or_update_log_message(
                        challenge.guild,
                        error(bold("Permission missing for kicking member!")),
                        logmsg,
                        member=challenge.member,
                    )
                return True

            roles = [
                challenge.guild.get_role(role)
                for role in await self.data.guild(challenge.guild).autoroles()
            ]
            try:
                await self.congratulation(challenge, roles)
                await self.remove_temprole(challenge)
                await self.send_or_update_log_message(
                    challenge.guild,
                    bold("Roles added, Captcha passed."),
                    logmsg,
                    member=challenge.member,
                )
            except MissingPermissions:
                roles_name = [role.name for role in roles]
                try:
                    await challenge.member.send(
                        f"Please contact the administrator of {challenge.guild.name} for obtaining "
                        "access of the server, I was unable to add you the roles on the server.\nYou "
                        f"should have obtained the following roles: "
                        f"{humanize_list(roles_name) if roles_name else 'None.'}"
                    )
                except discord.Forbidden:
                    await challenge.channel.send(
                        challenge.member.mention
                        + ": "
                        + f"Please contact the administrator of {challenge.guild.name} for obtaining "
                        "access of the server, I was unable to add you the roles on the server.\nYou "
                        f"should have obtained the following roles: "
                        f"{humanize_list(roles_name) if roles_name else 'None.'}",
                        delete_after=10,
                    )
                await self.send_or_update_log_message(
                    challenge.guild,
                    error(bold("Permission missing for giving roles! Member alerted.")),
                    logmsg,
                    member=challenge.member,
                )

        finally:
            try:
                await challenge.cleanup_messages()
            except MissingPermissions:
                await self.send_or_update_log_message(
                    challenge.guild,
                    error(bold("Missing permissions for deleting all messages for verification!")),
                    challenge.messages.get("logs"),
                    member=challenge.member,
                )
        return True

    async def congratulation(self, challenge: Challenge, roles: list) -> None:
        """
        Congrats to a member! He finished the captcha!
        """
        # Admin may have set channel to be DM, checking for manage_roles is useless since
        # it always return False, instead, we're taking a random text channel of the guild
        # to check our permission for kicking.
        channel = (
            challenge.guild.text_channels[0]
            if isinstance(challenge.channel, discord.DMChannel)
            else challenge.channel
        )

        if not channel.permissions_for(self.bot.get_guild(challenge.guild.id).me).manage_roles:
            raise MissingPermissions('Bot miss the "manage_roles" permission.')

        await challenge.member.add_roles(*roles, reason="Passed Captcha successfully.")

    async def nicely_kick_user_from_challenge(self, challenge: Challenge, reason: str) -> bool:
        # We're gonna check our permission first, to avoid DMing the user for nothing.

        # Admin may have set channel to be DM, checking for kick_members is useless since
        # it always return False, instead, we're taking a random text channel of the guild
        # to check our permission for kicking.
        channel = (
            challenge.guild.text_channels[0]
            if isinstance(challenge.channel, discord.DMChannel)
            else challenge.channel
        )

        if not channel.permissions_for(self.bot.get_guild(challenge.guild.id).me).kick_members:
            raise MissingPermissions('Bot miss the "kick_members" permission.')

        with suppress(discord.Forbidden, discord.HTTPException):
            await challenge.member.send(embed=build_kick_embed(challenge.guild, reason))
        try:
            await challenge.guild.kick(challenge.member, reason=reason)
        except discord.Forbidden:
            raise MissingPermissions("Unable to kick member.")
        return True

    # PLEASE DON'T TOUCH THOSE FUNCTIONS WITH YOUR COG OR EVAL. Thanks. - Pred
    # Those should only be used by the cog - 4 bags of None of your business.

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """
        This will put some text at the top of the main help. ([p]help Captcha)
        Thank to Sinbad.
        """
        pre_processed = super().format_help_for_context(ctx)
        return "{pre_processed}\n\n**Author**: {authors}\n**Version**: {version}".format(
            pre_processed=pre_processed,
            authors=humanize_list(self.__author__),
            version=self.__version__,
        )

    async def red_delete_data_for_user(self, **kwargs):
        return

    async def _initialize(self, send_patchnote: bool = True) -> None:
        """
        An initializer for the cog.
        It just set the logging level and send the patchnote if asked.
        """
        log_level = await self.data.log_level()
        log.setLevel(log_level)
        log.info("Captcha logging level has been set to: {lev}".format(lev=log_level))
        log.debug(
            "This logging level is reserved for testing and monitoring purpose, set the "
            "level to 2 if you prefer to be alerted by less minor events or doesn't want to help "
            "debugging this cog."
        )
        if send_patchnote:
            await self._send_patchnote()

        await self.data.was_loaded_once.set(True)

    async def _send_patchnote(self) -> None:
        await self.bot.wait_until_red_ready()
        self.patchnoteconfig = notice = Config.get_conf(
            None,
            identifier=4145125452,
            cog_name="PredeactorNews",
        )
        notice.register_user(version="0")
        async with notice.get_users_lock():
            old_patchnote_version: str = await notice.user(self.bot.user).version()
            if old_patchnote_version != __patchnote_version__:
                # Determine if this is the first time the user is using the cog (Not a change
                # of repo, see https://github.com/fixator10/Fixator10-Cogs/pull/163)
                if __patchnote_version__ == "2" and (not await self.data.was_loaded_once()):
                    await notice.user(self.bot.user).version.set(__patchnote_version__)
                    return

                log.info("New version of patchnote detected! Delivering... (¬‿¬ )")
                await self.bot.send_to_owners(self.patchnote)
                await notice.user(self.bot.user).version.set(__patchnote_version__)


def setup(bot: Red):
    cog = Captcha(bot)
    bot.add_cog(cog)
    # noinspection PyProtectedMember
    bot.loop.create_task(cog._initialize())
