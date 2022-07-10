# Discord/Red related
import logging

# Local
from abc import ABCMeta
from traceback import format_exception

from discord import Forbidden, Member
from redbot.core import commands
from redbot.core.utils.chat_formatting import bold, error

from .abc import MixinMeta
from .api import Challenge
from .errors import AlreadyHaveCaptchaError, SkipCaptcha

log = logging.getLogger("red.fixator10-cogs.captcha")


class Listeners(MixinMeta, metaclass=ABCMeta):
    async def runner(self, member: Member):
        allowed = await self.basic_check(member)
        if allowed:
            challenge = await self.create_challenge_for(member)
            # noinspection PyBroadException
            try:
                await self.realize_challenge(challenge)
            except SkipCaptcha:
                return
            except Exception as e:
                log.critical(
                    f"An unexpected error happened!\n"
                    f"Guild Name & ID: {challenge.guild.name} | {challenge.guild.id}\n"
                    f"Error: {format_exception(type(e), e, e.__traceback__)}"
                )
            finally:
                await self.delete_challenge_for(member)

    async def cleaner(self, member: Member):
        try:
            challenge = self.obtain_challenge(member)
        except KeyError:
            return
        try:
            await challenge.cleanup_messages()
            await self.send_or_update_log_message(
                challenge.guild,
                bold("User has left the server."),
                challenge.messages["logs"],
                member=challenge.member,
            )
        except Exception as e:
            log.critical(
                f"An unexpected error happened!\n"
                f"Guild Name & ID: {challenge.guild.name} | {challenge.guild.id}"
                f"Error: {format_exception(type(e), e, e.__traceback__)}"
            )
        finally:
            await self.delete_challenge_for(member)

    async def skip_challenge(self, author: Member, challenge: Challenge):
        try:
            challenge.skip_captcha = True
            challenge.cancel_tasks()
            roles = [
                challenge.guild.get_role(role)
                for role in await self.data.guild(challenge.guild).autoroles()
            ]
            await self.congratulation(challenge, roles)
            await self.remove_temprole(challenge)

            await self.send_or_update_log_message(
                challenge.guild,
                f"✅ Captcha skipped by {author.mention}.",
                challenge.messages["logs"],
                allowed_tries=(challenge.trynum, challenge.limit),
                member=challenge.member,
            )
            await self.send_or_update_log_message(
                challenge.guild,
                bold("Roles added, Captcha skipped."),
                challenge.messages["logs"],
                member=challenge.member,
            )
        except commands.MissingPermissions:
            try:
                await challenge.member.send(
                    f"Please contact the administrator of {challenge.guild.name} in order to obtain "
                    "access to the server, I was unable to give you the roles on the server."
                )
            except Forbidden:
                await challenge.channel.send(
                    challenge.member.mention
                    + ": "
                    + f"Please contact the administrator of {challenge.guild.name} in order to obtain "
                    "access to the server, I was unable to give you the roles on the server.",
                    delete_after=10,
                )
            logmsg = challenge.messages["logs"]
            await self.send_or_update_log_message(
                challenge.guild,
                error(bold("Permission missing for giving roles! Member alerted.")),
                logmsg,
                member=challenge.member,
            )
        finally:
            try:
                await challenge.cleanup_messages()
            except commands.MissingPermissions:
                await self.send_or_update_log_message(
                    challenge.guild,
                    error(bold("Missing permissions for deleting all messages for verification!")),
                    challenge.messages.get("logs"),
                    member=challenge.member,
                )
        return True

    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        await self.runner(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        await self.cleaner(member)

    @commands.guildowner()
    @commands.command()
    async def captcha(self, ctx, *members: Member):
        """Start a captcha challenge for the specified members."""
        await ctx.send("Running Captcha challenges... this may take a while!")
        async with ctx.typing():
            time = await self.data.guild(ctx.guild).timeout()
            await self.data.guild(ctx.guild).timeout.set(20)
            for member in members:
                try:
                    await self.runner(member)
                except AlreadyHaveCaptchaError:
                    await ctx.send(
                        f"The user {member.display_name} ({member.id}) already have a captcha challenge running."
                    )
            await self.data.guild(ctx.guild).timeout.set(time)
        message = (
            "**The challenge has finished for the following members:**\n(unless the user already had a challenge in progress)\n"
            + ", ".join(member.display_name for member in members if not member.bot)
        )
        if any(member.bot for member in members):
            message += (
                "\n\n**The following members were not challenged because they were bots:**\n"
                + ", ".join(member.display_name for member in members if member.bot)
            )
        await ctx.send(message)

    @commands.admin_or_permissions(manage_guild=True)
    @commands.command(aliases=["bypasscaptcha"])
    async def skipcaptcha(self, ctx: commands.Context, *members: Member):
        """Cancel a captcha challenge for the specified members."""
        await ctx.send("Cancelling Captcha challenges...")
        async with ctx.typing():
            cancelled_challenge = []
            for member in members:
                try:
                    challenge = self.obtain_challenge(member)
                except KeyError:
                    await ctx.send(
                        f"The user {member.display_name} ({member.id}) is not challenging any Captcha."
                    )
                else:
                    cancelled_challenge.append(member)
                    try:
                        await self.skip_challenge(ctx.author, challenge)
                    except Exception:
                        pass
                    finally:
                        await self.delete_challenge_for(member)
        message = "**The challenge has cancelled for the following members:**\n" + ", ".join(
            member.display_name
            for member in members
            if not member.bot and member in cancelled_challenge
        )
        await ctx.send(message)
