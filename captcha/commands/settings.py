# Builtin or Pip
from abc import ABCMeta
from random import choice
from typing import Union

# Discord/Red related
import discord
import redbot.core.utils.chat_formatting as form
from redbot.core import commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

# Local
from ..abc import MixinMeta
from ..utils import (
    build_embed_with_missing_permissions,
    build_embed_with_missing_settings,
    check_permissions_in_channel,
)


class Settings(MixinMeta, metaclass=ABCMeta):
    """
    Commands used for setting up Captcha.
    Those commands are mostly used in a guild.
    """

    @commands.guild_only()
    @commands.admin()
    @commands.group(name="setcaptcha", aliases=["captchaset"])
    async def config(self, ctx: commands.GuildContext):
        """Configure Captcha in your server."""
        pass

    config: commands.Group

    @config.command(name="channel", usage="<text_channel_or_'dm'>")
    async def challenge_channel(
        self, ctx: commands.Context, *, destination: Union[discord.TextChannel, str]
    ):
        """Set the channel where the user will be challenged.

        ``destination``: Text channel.
        If you want to use user's private message, use `dm`.
        """

        is_text_channel = isinstance(destination, discord.TextChannel)
        if not is_text_channel and destination != "dm":
            await ctx.send_help()
            await ctx.send(
                form.error(
                    "You can only use 'dm' as the destination if you don't want to use a channel."
                )
            )
            return

        if is_text_channel:
            if needperm := await check_permissions_in_channel(
                [
                    "add_reactions",
                    "embed_links",
                    "kick_members",
                    "manage_messages",
                    "read_messages",
                    "read_message_history",
                    "send_messages",
                    "manage_roles",
                    "attach_files",
                ],
                destination,
            ):
                await ctx.send(embed=await build_embed_with_missing_permissions(needperm))
                return

        await self.data.guild(ctx.guild).channel.set(
            destination.id if is_text_channel else destination
        )
        await ctx.send(
            form.info(
                "Destination registered: {dest}.".format(
                    dest=destination.mention if is_text_channel else "User Private Message"
                )
            )
        )

    @config.command(
        name="logschannel",
        aliases=["lchann", "lchannel", "logschan", "logchannel", "logsc"],
        usage="<text_channel_or_'none'>",
    )
    async def logging_channel(
        self, ctx: commands.Context, *, destination: Union[discord.TextChannel, str]
    ):
        """Set a channel where events are registered.

        The following actions will be registered:
        - User join and must answer the captcha.
        - User passed captcha/failed captcha.
        - User got kicked.

        ``destination``: Text channel.
        You can also use "None" if you wish to remove the logging channel.
        """

        if not isinstance(destination, discord.TextChannel):
            if destination.lower() == "none":
                await self.data.guild(ctx.guild).logschannel.clear()
                await ctx.send(form.info("Logging channel removed."))
            else:
                await ctx.send(form.error("Invalid destination."))
            return

        if needperm := await check_permissions_in_channel(
            [
                "read_messages",
                "read_message_history",
                "send_messages",
                "attach_files",
            ],
            destination,
        ):
            await ctx.send(embed=await build_embed_with_missing_permissions(needperm))
            return

        await self.data.guild(ctx.guild).logschannel.set(destination.id)
        await ctx.send(
            form.info("Logging channel registered: {chan}.".format(chan=destination.mention))
        )

    @config.command(name="enable", aliases=["activate"], usage="<true_or_false>")
    async def activator(self, ctx: commands.Context, state: bool):
        """Enable or disable Captcha security.

        Use `True` (Or `yes`) to enable or `False` (or `no`) to disable.
        Users won't be challenged and will not receive any temporary role if disabled.
        """
        config = await self.data.guild(ctx.guild).all()

        if config["channel"] is None:
            await ctx.send(embed=await build_embed_with_missing_settings(["channel"]))
            return
        is_dm = config["channel"] == "dm"

        actual_state = config["enabled"]
        if actual_state is state:
            await ctx.send(
                form.warning(form.bold("Captcha is already set on {stat}.".format(stat=state)))
            )
            return

        if is_dm:
            perms = ["kick_members", "manage_roles"]
        else:
            perms = [
                "add_reactions",
                "embed_links",
                "kick_members",
                "manage_messages",
                "read_messages",
                "read_message_history",
                "send_messages",
                "manage_roles",
                "attach_files",
            ]

        if needperm := await check_permissions_in_channel(
            perms,
            self.bot.get_channel(config["channel"]) if not is_dm else ctx.channel,
        ):
            await ctx.send(embed=await build_embed_with_missing_permissions(needperm))
            return

        await self.data.guild(ctx.guild).enabled.set(state)
        await ctx.send(form.info("Captcha state registered: {stat}".format(stat=state)))

    @config.command(name="type", usage="<type_of_captcha>")
    async def captcha_type_setter(self, ctx: commands.Context, captcha_type: str):
        """
        Change the type of Captcha challenge.

        You choose the following type of Captcha:
        - image: A normal captcha image, hardest to understand.
        - wheezy: A less complex captcha image, easier than image method.
        - plain: Plain text captcha. Easiest to read, cannot be copy/pasted.
        """

        available = ("wheezy", "image", "plain")
        captcha_type = captcha_type.lower()
        if captcha_type not in available:
            await ctx.send_help()
            await ctx.send(
                form.error(
                    form.bold(
                        "{type} is not a valid Captcha type option.".format(
                            type=form.bordered(captcha_type)
                        )
                    )
                )
            )
            return

        await self.data.guild(ctx.guild).type.set(captcha_type)
        await ctx.send(form.info("Captcha type registered: {type}".format(type=captcha_type)))

    @config.command(name="timeout", usage="<time_in_minutes>")
    async def timeout_setter(self, ctx: commands.Context, time: int):
        """
        Set the timeout before the bot kick the user if the user doesn't answer.

        Time will be expressed in minutes.
        """
        if time > 15:
            await ctx.send("Time cannot be more than 15.")
            return
        if time < 1:
            await ctx.send("Time must be more than 0.")

        await self.data.guild(ctx.guild).timeout.set(time)
        await ctx.send(
            form.info(
                "Timeout registered: {time} minute{plur}.".format(
                    time=time, plur="s" if time > 1 else ""
                )
            )
        )

    @config.command(name="temprole", usage="<temporary_role_or_'none'>")
    async def temporary_role_setter(
        self, ctx: commands.Context, *, role: Union[discord.Role, str]
    ):
        """
        Give a temporary role when initilalizing the captcha challenge.

        This role will be added while the user must answer the captcha.
        """
        if not isinstance(role, (discord.Role, str)):
            await ctx.send('Converting to "discord.Role" or "str" failed for parameter "role".')
            return
        if isinstance(role, str):
            if role.lower() == "none":
                await self.data.guild(ctx.guild).temprole.clear()
                await ctx.send("Cleared.")
            else:
                await ctx.send(
                    'Converting to "discord.Role" or "str" failed for parameter "role".'
                )
                # EEEHHHH C'EST LE DAB DU J'M'EN BAT ROYAL LES COUILLES
            return

        if needperm := await check_permissions_in_channel(["manage_roles"], ctx.channel):
            await ctx.send(embed=await build_embed_with_missing_permissions(needperm))
            return

        if role.position >= ctx.me.top_role.position:
            await ctx.send("This role is higher than my highest role in the discord hierarchy.")
            return
        if role.position >= ctx.author.top_role.position:
            await ctx.send("This role is higher than your own in the discord hierarchy.")
            return

        await self.data.guild(ctx.guild).temprole.set(role.id)
        await ctx.send(form.info("Temporary role registered: {role}".format(role=role.name)))

    @config.command(name="allowedretries", usage="<number_of_retry>")
    async def retries_setter(self, ctx: commands.Context, number_of_retries: int):
        """
        Set the number of retries allowed before getting kicked.
        """
        if number_of_retries < 1:
            await ctx.send("The number of retries cannot be less than 1.")
            return

        await self.data.guild(ctx.guild).retry.set(number_of_retries)
        await ctx.send(f"Alright, it's been set to {str(number_of_retries)}")

    # Taken from my logic at
    # https://github.com/SharkyTheKing/Sharky/blob/master/verify/verification.py, thank buddy
    # What the f*ck do you mean I'm lazy? Dude I made 3/4 of the cog and logic in less a week, I
    # deserve understanding what sleep schedule mean!

    @config.group(invoke_without_command=True)
    async def autorole(self, ctx: commands.GuildContext):
        """
        Set the roles to give when passing the captcha.
        """
        if needperm := await check_permissions_in_channel(["manage_roles"], ctx.channel):
            await ctx.send(embed=await build_embed_with_missing_permissions(needperm))
            return False
        await ctx.send_help()

    @autorole.command(name="add")
    async def add_roles(self, ctx: commands.Context, *roles: discord.Role):
        """Add a role to give.
        You can give more than one role to add.

        Use double quotes if the role contains spaces.
        """
        if not roles:
            await ctx.send_help()
            return
        if await check_permissions_in_channel(["manage_roles"], ctx.channel):
            return

        message = ""
        added = []
        already_added = []
        error = {}

        for role in roles:
            async with self.data.guild(ctx.guild).autoroles() as roles_list:
                if role.position >= ctx.me.top_role.position:
                    error[
                        role.name
                    ] = "This role is higher than my highest role in the role hierarchy."
                    continue
                if role.position >= ctx.author.top_role.position:
                    error[
                        role.name
                    ] = "This role is higher than your own in the discord hierarchy."
                    continue
                if role.id not in roles_list:
                    roles_list.append(role.id)
                    added.append(role.name)
                else:
                    already_added.append(role.name)

        if added:
            message += "\nAdded role(s): {roles}".format(roles=form.humanize_list(added))
        if already_added:
            message += "\nRole(s) already added: {roles}".format(
                roles=form.humanize_list(already_added)
            )
        if error:
            message += "\nCannot add the following role(s)"
            for role in error.items():
                message += "\n{rolename}: {reason}".format(rolename=role[0], reason=role[1])
        if message:
            for line in form.pagify(message):
                await ctx.send(line)

    @autorole.command(name="remove", aliases=["delete", "rm"])
    async def remove_roles(self, ctx: commands.Context, *roles: discord.Role):
        """Remove a role to give.
        You can give more than one role to add.
        """
        if not roles:
            await ctx.send_help()
            return
        if await check_permissions_in_channel(["manage_roles"], ctx.channel):
            return

        message = ""
        removed = []
        not_found = []
        error = {}

        async with self.data.guild(ctx.guild).autoroles() as roles_list:
            for role in roles:
                if role.position >= ctx.author.top_role.position:
                    error[
                        role.name
                    ] = "This role is higher than your own in the discord hierarchy."
                    continue
                if role.id in roles_list:
                    roles_list.remove(role.id)
                    removed.append(role.name)
                else:
                    not_found.append(role.name)

        if not_found:
            message += "\nRole(s) not found in autorole list: {roles}".format(
                roles=form.humanize_list(not_found)
            )
        if removed:
            message += "\nRole(s) remove from autorole list: {roles}".format(
                roles=form.humanize_list(removed)
            )
        if error:
            message += "\nCannot remove the following role(s)"
            for role in error.items():
                message += "\n{rolename}: {reason}".format(rolename=role[0], reason=role[1])
        if message:
            for line in form.pagify(message):
                await ctx.send(line)

    @autorole.command(name="list")
    async def list_roles(self, ctx: commands.Context):
        """
        List all roles that will be given.
        """
        all_roles = await self.data.guild(ctx.guild).autoroles()
        maybe_not_found = []
        message = ""

        for role in all_roles:
            fetched_role = ctx.guild.get_role(role)
            if not fetched_role:
                maybe_not_found.append(fetched_role.id)
                continue
            message += "- {name} (`{id}`).\n".format(name=fetched_role.name, id=fetched_role.id)

        if maybe_not_found:
            clean_list = list(set(all_roles) - set(maybe_not_found))
            await self.data.guild(ctx.guild).autoroles.set(clean_list)
            message += "\nSome roles has been removed since I was unable to find them."
        if message:
            for line in form.pagify(message):
                await ctx.send(line)
        else:
            await ctx.send("No role has been added.")

    @config.command(name="forgetme")
    async def forget_guild_settings(self, ctx: commands.Context):
        """Delete guild's data."""
        msg = await ctx.send(
            form.warning(form.bold("Are you sure you want me to forget all settings?"))
        )
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result:
            await self.data.guild(ctx.guild).clear()
            await ctx.send("Done!")
            return
        await ctx.send("Aborted.")
