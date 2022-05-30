import asyncio
import logging
from typing import Union

import discapty
import discord
from redbot.core.bot import Red
from redbot.core.commands import MissingPermissions
from redbot.core.utils import chat_formatting as form
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate

from .errors import AskedForReload, LeftServerError, MissingRequiredValueError

log = logging.getLogger("red.predeactor.captcha")


def ok_check(msg: str):
    return f"✅ {msg}"


class Challenge:
    """Representation of a challenge an user is doing."""

    def __init__(self, bot: Red, member: discord.Member, data: dict):
        self.bot: Red = bot

        self.member: discord.Member = member
        self.guild: discord.Guild = member.guild
        self.config: dict = data  # Will contain the config of the guild.

        if not self.config["channel"]:
            raise MissingRequiredValueError("Missing channel for verification.")
        self.channel: Union[discord.TextChannel, discord.DMChannel] = (
            bot.get_channel(self.config["channel"])
            if self.config.get("channel") != "dm"
            else self.member.dm_channel
        )

        self.type: str = self.config["type"]

        self.messages: dict = {}
        # bot_challenge: Message send for the challenge, contain captcha.
        # logs: The message that has been sent in the logging channel.
        # answer: Member's answer to captcha, may or may not exist.
        self.log = bot.get_cog("Captcha").send_or_update_log_message

        self.running: bool = False
        self.tasks: list = []
        self.limit: int = self.config["retry"]
        self.trynum: int = 0

        self.captcha: discapty.Captcha = discapty.Captcha(self.type)

    async def try_challenging(self) -> bool:
        """Do challenging in one function!

        This auto reload the captcha if needed.
        This does not try to get errors.
        This does not gives role.
        """

        if self.running is True:
            raise OverflowError("A Challenge is already running.")

        if self.messages.get("bot_challenge"):
            await self.reload()
        else:
            await self.send_basics()

        self.running = True
        self.messages["logs"] = logmsg = await self.log(
            self.guild,
            form.info("The member started the challenge."),
            self.messages.get("logs", None),
            allowed_tries=(self.trynum, self.limit),
            member=self.member,
        )

        try:
            received = await self.wait_for_action()
            if received is None:
                raise LeftServerError("User has left guild.")
            if hasattr(received, "content"):
                # It's a message!
                self.messages["answer"] = received
                error_message = ""
                try:
                    state = await self.verify(received.content)
                except discapty.SameCodeError:
                    error_message += form.error(form.bold("Code invalid. Do not copy and paste."))
                    state = False
                else:
                    if not state:
                        error_message += form.warning("Code invalid.")
                if error_message:
                    await self.channel.send(error_message, delete_after=3)
                    await self.log(
                        self.guild,
                        form.error("User sent an invalid code."),
                        logmsg,
                        allowed_tries=(self.trynum, self.limit),
                        member=self.member,
                    )
            else:
                await self.log(
                    self.guild,
                    "🔁 User reloaded captcha.",
                    logmsg,
                    allowed_tries=(self.trynum, self.limit),
                    member=self.member,
                )
                raise AskedForReload("User want to reload Captcha.")
        finally:
            self.running = False
        if state:
            await self.log(
                self.guild,
                ok_check("User passed captcha."),
                logmsg,
                allowed_tries=(self.trynum, self.limit),
                member=self.member,
            )
        return state

    async def send_basics(self) -> None:
        """
        Send the message containing the captcha code.
        """
        if self.messages.get("bot_challenge"):
            raise OverflowError("Use 'Challenge.reload' to create another code.")

        embed_and_file = await self.captcha.generate_embed(
            guild_name=self.guild.name,
            author={"name": f"Captcha for {self.member.name}", "url": self.member.avatar_url},
            footer={"text": f"Tries: {self.trynum} / Limit: {self.limit}"},
            title=f"{self.guild.name} Verification System",
            description=(
                "Please return me the code on the following image. The code is made of 8 "
                "characters."
            ),
        )

        try:
            await asyncio.sleep(1)
            bot_message: discord.Message = await self.channel.send(
                content=self.member.mention,
                embed=embed_and_file["embed"],
                file=embed_and_file["image"],
                delete_after=900,  # Delete after 15 minutes.
            )
        except discord.Forbidden:
            raise MissingPermissions("Cannot send message in verification channel.")
        self.messages["bot_challenge"] = bot_message
        try:
            await bot_message.add_reaction("🔁")
        except discord.Forbidden:
            raise MissingPermissions("Cannot react in verification channel.")

    async def wait_for_action(self) -> Union[discord.Reaction, discord.Message, None]:
        """Wait for an action from the user.

        It will return an object of discord.Message or discord.Reaction depending what the user
        did.
        """
        self.cancel_tasks()  # Just in case...
        self.tasks = self._give_me_tasks()
        done, pending = await asyncio.wait(
            self.tasks,
            timeout=self.config["timeout"] * 60,
            return_when=asyncio.FIRST_COMPLETED,
        )
        self.cancel_tasks()
        if len(done) == 0:
            raise TimeoutError("User didn't answer.")
        try:  # An error is raised if we return the result and when the task got cancelled.
            return done.pop().result()
        except asyncio.CancelledError:
            return None

    async def reload(self) -> None:
        """
        Resend another message with another code.
        """
        if not self.messages.get("bot_challenge", None):
            raise AttributeError(
                "There is not message to reload. Use 'Challenge.send_basics' first."
            )

        old_message: discord.Message = self.messages["bot_challenge"]
        try:
            await old_message.delete()
        except (discord.Forbidden, discord.HTTPException):
            log.warning(
                "Bot was unable to delete previous message in {guild}, ignoring.".format(
                    guild=self.guild.name
                )
            )

        self.captcha.code = discapty.discapty.random_code()
        embed_and_file = await self.captcha.generate_embed(
            guild_name=self.guild.name,
            title="{guild} Verification System".format(guild=self.guild.name),
            footer={"text": f"Tries: {self.trynum} / Limit: {self.limit}"},
            description=(
                "Please return me the code on the following image. The code is made of 8 "
                "characters."
            ),
        )

        try:
            bot_message: discord.Message = await self.channel.send(
                embed=embed_and_file["embed"],
                file=embed_and_file["image"],
                delete_after=900,  # Delete after 15 minutes.
            )
        except discord.Forbidden:
            raise MissingPermissions("Cannot send message in verification channel.")
        self.messages["bot_challenge"] = bot_message
        try:
            await bot_message.add_reaction("🔁")
        except discord.Forbidden:
            raise MissingPermissions("Cannot react in verification channel.")

    async def verify(self, code_input: str) -> bool:
        """Verify a code."""
        return await self.captcha.verify_code(code_input)

    def cancel_tasks(self) -> None:
        """Cancel the ongoing tasks."""
        for task in self.tasks:
            task: asyncio.Task
            if not task.done():
                task.cancel()

    async def cleanup_messages(self) -> bool:
        """
        Remove every stocked messages.

        Return a boolean, if the deletion was successful.
        """
        errored = False
        for message in self.messages.items():
            if message[0] == "bot_challenge":
                self.cancel_tasks()
            if message[0] == "logs":
                # We don't want to delete logs.
                continue
            try:
                await message[1].delete()
                del message
            except discord.Forbidden:
                if not isinstance(self.channel, discord.DMChannel):
                    # We're fine with not deleting user's message if it's in DM.
                    raise MissingPermissions("Cannot delete message.")
            except discord.HTTPException:
                errored = True
        return not errored  # Return if deleted, contrary of erroring, big brain

    def _give_me_tasks(self) -> list:
        def leave_check(u):
            return u.id == self.member.id

        return [
            asyncio.create_task(
                self.bot.wait_for(
                    "reaction_add",
                    check=ReactionPredicate.with_emojis(
                        "🔁", message=self.messages["bot_challenge"], user=self.member
                    ),
                )
            ),
            asyncio.create_task(
                self.bot.wait_for(
                    "message",
                    check=MessagePredicate.same_context(
                        channel=self.channel,
                        user=self.member,
                    ),
                )
            ),
            asyncio.create_task(self.bot.wait_for("user_remove", check=leave_check)),
        ]


# class ListenersAPI:
#     @commands.Cog.listener()
#     async def on_predeactor_captcha_pass(self, captcha_class: Challenge):
#         pass
#
#     @commands.Cog.listener()
#     async def on_predeactor_captcha_fail(self, captcha_class: Challenge):
#         pass
#
#     @commands.Cog.listener()
#     async def on_predeactor_captcha_ask_reload(self, captcha_class: Challenge):
#         pass
