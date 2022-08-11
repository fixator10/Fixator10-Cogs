# General TODO:
# Remove all "# type: ignore" once we have bumped discord.py to 2.0
# The reasons those have been added is because `ctx.guild`'s signature before 2.0 is
# "cached_property | Unknown" for Pylance, hence, `GuildSettings.from_guild` or related does not
# appreciate these types. This has been fixed on 2.0 where typehint has been especially specified.

import json
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, Optional, Union

import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting as formatting
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from .abc import CogABC
from .config import GuildSettings
from .errors import MissingRequiredPermissionsError, MissingRequiredSettingError


async def send_modified_changes(changes: Dict[str, Any], ctx: commands.Context):
    template = formatting.info("**Changes committed:**\n\n")
    if changes:
        for key, value in changes.items():
            template += f"{formatting.inline(key)}: Set to {formatting.inline(str(value))}\n"
    else:
        template += "No changes were made."
    await ctx.send(template)


class Commands(CogABC):
    @commands.guild_only()
    @commands.group(name="captchaset", aliases=["setcaptcha"])
    async def captcha_set(self, _: commands.GuildContext):
        """
        Configure Captcha in your server.
        """

    @captcha_set.command(name="export")
    @commands.has_permissions(embed_links=True)
    async def captcha_set_export(self, ctx: commands.GuildContext):
        """
        Export this server's settings for Captcha.
        """
        config = await GuildSettings.from_guild(ctx.guild)

        embed = discord.Embed(
            title="Captcha - Configuration", color=await self.bot.get_embed_color(ctx)
        )

        challenge_channel, logging_channel = ctx.guild.get_channel(
            config.channel
        ), ctx.guild.get_channel(config.logs_channel)
        embed.add_field(name="Challenge Channel", value=str(challenge_channel))
        embed.add_field(name="Logging Channel", value=str(logging_channel))
        embed.add_field(name="Captcha Type", value=str(config.type))
        embed.add_field(name="Is Enabled", value=str(config.enabled))

        temp_role = ctx.guild.get_role(config.temp_role) if config.temp_role else None
        embed.add_field(name="Temporary Role", value=str(temp_role))

        embed.add_field(name="Timeout", value=str(config.timeout))
        embed.add_field(name="Allowed attempts", value=str(config.retries))

        has_file_permission: bool = False
        if ctx.me.permissions_in(ctx.channel).attach_files:
            has_file_permission = True

        config_output = StringIO(json.dumps(config.to_dict(), indent=2))
        await ctx.send(
            embed=embed,
            file=(
                discord.File(
                    config_output,
                    filename=f"captcha-config-report-{ctx.guild.name.lower()}-{round(datetime.now(timezone.utc).timestamp())}.json",
                )
                if has_file_permission
                else None
            ),
        )

    @captcha_set.group(name="channels", aliases=["channel", "c"])
    async def captcha_set_channels(self, _: commands.GuildContext):
        """
        Set the channels used by Captcha.
        """

    @captcha_set_channels.command(name="challenge", aliases=["c"])
    async def captcha_set_channel_challenge(
        self, ctx: commands.GuildContext, *, channel: Union[discord.TextChannel, str]
    ):
        """
        Set the channel where the new user will be challenged.

        __Parameters__
        ```channel```: ```Text Channel``` or ```string``` (Required)
            The channel where you want to send the challenges.
            You can either use a text channel from your server, or to send challenges in user's private message, pass ```dm``` as the channel.
        """
        config = await GuildSettings.from_guild(ctx.guild)

        if isinstance(channel, str) and (channel != "dm"):
            return await ctx.send(
                formatting.error("Can't accept this channel: Only a channel can be used or 'dm'.")
            )
        config.channel = channel
        await send_modified_changes(config.dirty, ctx)

        await config.commit()

    @captcha_set_channels.command(name="logs", aliases=["l"])
    async def captcha_set_channel_logs(
        self, ctx: commands.GuildContext, *, channel: discord.TextChannel
    ):
        """
        Set the channel where the logs will be sent.

        __Parameters__
        ```channel```: ```Text Channel``` (Required)
            The channel to set.
        """
        config = await GuildSettings.from_guild(ctx.guild)
        config.logs_channel = channel
        await send_modified_changes(config.dirty, ctx)
        await config.commit()

    @captcha_set.command(name="type")
    async def captcha_set_type(self, ctx: commands.GuildContext, *, captcha_type: str):
        """
        Set the type of Captcha to send.

        __Parameters__
        ```captcha_type```: ```wheezy```, ```image``` or ```text``` (Required)
            The type to use. Following are links for examples.
            - Wheezy: https://imgur.com/a/l9V09PN
            - Image: https://imgur.com/a/wozYgW0
        """
        captcha_type = captcha_type.lower()
        if captcha_type not in (
            "wheezy",
            "image",
            "text",
        ):
            return await ctx.send(
                "Can't accept this type: Only 'wheezy', 'image' or 'text' is allowed."
            )

        config = await GuildSettings.from_guild(ctx.guild)
        config.type = captcha_type

    @captcha_set.command(name="enable", aliases=["activate"])
    async def captcha_set_enable(self, ctx: commands.GuildContext, state: bool):
        """
        Enable or disable Captcha in your server.

        __Parameters__
        ```state```: ```boolean``` (Required)
            To enable or disable the Captcha module.
        """
        config = await GuildSettings.from_guild(ctx.guild)

        template_error = formatting.error("Cannot enable Captcha:\n\n")

        try:
            config.can_be_enabled(ctx)
        except MissingRequiredSettingError as error:
            template_error += f"The setting {formatting.inline(error.setting)} does not comply for activation. (Actual value: {formatting.inline(str(error.actual_value))})"
            return await ctx.send(template_error)
        except MissingRequiredPermissionsError as error:
            template_error += "The bot is missing one or more permissions: "
            template_error += ", ".join(
                [
                    f"{formatting.inline(perm.replace('_', ' ').title())}"
                    for perm in error.permissions
                ]
            )
            if error.in_destination:
                template_error += f"\nThese permissions might miss in the following channel: {formatting.inline(error.in_destination)}"
            return await ctx.send(template_error)

        config.enabled = state

        await send_modified_changes(config.dirty, ctx)
        await config.commit()

    @captcha_set.command(name="timeout")
    async def captcha_set_timeout(self, ctx: commands.GuildContext, *, time: int):
        """
        Set the timeout before kicking a member if they do not complete the captcha in time.

        __Parameters__
        ```time```: ```number``` (Required)
            The time in minute to set. Expressed in minutes.
        """
        if time > 15:
            return await ctx.send("The time cannot be more than 15 minutes.")
        if time < 1:
            return await ctx.send("The time cannot be less than 1 minute.")

        config = await GuildSettings.from_guild(ctx.guild)
        config.timeout = time

        await send_modified_changes(config.dirty, ctx)
        await config.commit()

    @captcha_set.group(name="roles")
    async def captcha_set_roles(self, _: commands.GuildContext):
        """
        Set the roles settings.
        """

    @captcha_set_roles.command(name="temprole")
    async def captcha_set_roles_temprole(self, ctx: commands.GuildContext, *, role: discord.Role):
        """
        Set the temporary role.

        The temporary role is a role that is given only for completing the captcha. It is removed after the captcha is completed.

        __Parameters__
        ```role```: ```Server Role``` (Optional)
            The temporary role to set.
            If omitted, the role will be removed.
        """
        config = await GuildSettings.from_guild(ctx.guild)
        config.temp_role = role
        await send_modified_changes(config.dirty, ctx)
        await config.commit()

    # Get ready Trusty, here goes nothing! - jk
    @captcha_set_roles.group(name="autoroles")
    async def captcha_set_roles_autoroles(self, ctx: commands.GuildContext):
        """
        Set the roles to give on completion.
        """
        config = await GuildSettings.from_guild(ctx.guild)
        result: Dict[int, discord.Role] = {}
        msg: str = ""

        for role_id in config.auto_roles:
            role: Optional[discord.Role] = ctx.guild.get_role(role_id)
            if role:
                result[role.id] = role

        if roles_not_found := list(config.auto_roles - result.keys()):
            config.auto_roles = result.values()
            msg = f"These role's IDs were removed because {ctx.me.display_name} was unable to find them (Most probably deleted):\n\n"
            msg += "\n".join(str(roles_not_found))

        if msg:
            await config.commit()
            await ctx.send(msg)

    @captcha_set_roles_autoroles.command(name="add")
    async def captcha_set_roles_autoroles_add(
        self, ctx: commands.GuildContext, *, role: discord.Role
    ):
        """
        Add a role to the list of roles to add.

        __Parameters__
        ```role```: ```Server Role``` (Required)
            The role to add.
        """
        config = await GuildSettings.from_guild(ctx.guild)
        new_list = config.auto_roles.copy()
        new_list.append(role.id)
        config.auto_roles = new_list
        await send_modified_changes(config.dirty, ctx)
        await config.commit()

    @captcha_set_roles_autoroles.command(name="remove")
    async def captcha_set_roles_autoroles_remove(
        self, ctx: commands.GuildContext, *, role: discord.Role
    ):
        """
        Remove a role to the list.

        __Parameters__
        ```role```: ```Server Role``` (Required)
            The role to remove.
        """
        config = await GuildSettings.from_guild(ctx.guild)
        new_list = config.auto_roles.copy()
        if role.id in new_list:
            new_list.remove(role.id)
        config.auto_roles = new_list
        await send_modified_changes(config.dirty, ctx)
        await config.commit()

    @captcha_set_roles_autoroles.command(name="list")
    async def captcha_set_roles_autoroles_list(self, ctx: commands.GuildContext):
        """
        Show the list of roles that has been set.
        """
        config = await GuildSettings.from_guild(ctx.guild)
        msg = "**Roles:**\n\n" if config.auto_roles else "**No roles were added.**"

        for role_id in config.auto_roles:
            fetched_role: Optional[discord.Role] = ctx.guild.get_role(role_id)
            if fetched_role:
                msg += f"{fetched_role.mention} ({fetched_role.name} - {formatting.inline(str(role_id))})\n"
            else:
                msg += f"Role not found ({formatting.inline(str(role_id))})"

        await ctx.send(msg, allowed_mentions=discord.AllowedMentions(roles=False))

    @captcha_set.command(name="concurrency")
    async def captcha_set_concurrency(self, ctx: commands.GuildContext, *, total: int):
        """
        Set the allowed concurrency of running challenges.

        In case more challenges are about to run than allowed by the concurrency, they'll be put into a queue where they must wait for there challenges.

        __Parameters__
        ```total```: ```Number``` (Required)
            The total of allowed challenges concurrency.
        """
        if not 10 >= total >= 1:
            # Not contained between 1 and 10
            return await ctx.send(
                formatting.error(f"The total must be contained between 1 and 10, not {total}")
            )
        config = await GuildSettings.from_guild(ctx.guild)
        config.simultaneous_challenges = total
        await send_modified_changes(config.dirty, ctx)
        await config.commit()

    @captcha_set.command(name="forget")
    async def captcha_set_clear(self, ctx: commands.GuildContext):
        """
        Delete the settings set in this server for Captcha cog.
        """
        msg = await ctx.send(
            formatting.warning(formatting.bold("Are you sure you want me to forget all settings?"))
        )
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)

        if pred.result:
            config = await GuildSettings.from_guild(ctx.guild)
            config.erase()
            await send_modified_changes(config.dirty, ctx)
            await config.commit()
            return await ctx.send("Settings deleted.")

        return await ctx.send("Phew, that was close... :)")
