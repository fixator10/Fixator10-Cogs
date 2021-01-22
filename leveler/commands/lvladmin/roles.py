from collections import OrderedDict
from typing import Union

import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from leveler.abc import MixinMeta

from .basecmd import LevelAdminBaseCMD


class Roles(MixinMeta):
    """Roles administration commands"""

    lvladmin = getattr(LevelAdminBaseCMD, "lvladmin")

    @lvladmin.group()
    async def role(self, ctx):
        """Admin role configuration."""
        pass

    @commands.mod_or_permissions(manage_roles=True)
    @role.command(name="link")
    @commands.guild_only()
    async def linkrole(
        self, ctx, add_role: discord.Role, level: int, remove_role: discord.Role = None
    ):
        """Associate a role with a level.

        Removes previous role if given."""
        server = ctx.guild

        server_roles = await self.db.roles.find_one({"server_id": str(server.id)})
        if not server_roles:
            new_server = {
                "server_id": str(server.id),
                "roles": {
                    add_role.name: {
                        "level": str(level),
                        "remove_role": remove_role.name if remove_role else None,
                    }
                },
            }
            await self.db.roles.insert_one(new_server)
        else:
            if add_role.name not in server_roles["roles"]:
                server_roles["roles"][add_role.name] = {}

            server_roles["roles"][add_role.name]["level"] = str(level)
            server_roles["roles"][add_role.name]["remove_role"] = (
                remove_role.name if remove_role else None
            )
            await self.db.roles.update_one(
                {"server_id": str(server.id)},
                {"$set": {"roles": server_roles["roles"]}},
            )

        if remove_role:
            await ctx.send(
                "The `{}` role has been linked to level `{}`. "
                "Will also remove `{}` role.".format(add_role, level, remove_role)
            )
        else:
            await ctx.send("The `{}` role has been linked to level `{}`".format(add_role, level))

    @commands.mod_or_permissions(manage_roles=True)
    @role.command(name="unlink", usage="<role>")
    @commands.guild_only()
    async def unlinkrole(self, ctx, *, role_to_unlink: Union[discord.Role, str]):
        """Delete a role/level association."""
        server = ctx.guild
        role_to_unlink = (
            role_to_unlink.name if isinstance(role_to_unlink, discord.Role) else role_to_unlink
        )

        server_roles = await self.db.roles.find_one({"server_id": str(server.id)})
        roles = server_roles["roles"]

        if role_to_unlink in roles:
            await ctx.send(
                "Role/Level association `{}`/`{}` removed.".format(
                    role_to_unlink, roles[role_to_unlink]["level"]
                )
            )
            del roles[role_to_unlink]
            await self.db.roles.update_one(
                {"server_id": str(server.id)}, {"$set": {"roles": roles}}
            )
        else:
            await ctx.send("The `{}` role is not linked to any levels!".format(role_to_unlink))

    @commands.mod_or_permissions(manage_roles=True)
    @role.command(name="listlinks")
    @commands.guild_only()
    async def listrole(self, ctx):
        """List level/role associations."""
        server = ctx.guild

        server_roles = await self.db.roles.find_one({"server_id": str(server.id)})

        if server_roles is None or not server_roles.get("roles"):
            msg = "None"
        else:
            sortorder = sorted(
                server_roles["roles"],
                key=lambda r: int(server_roles["roles"][r]["level"]),
            )
            roles = OrderedDict(server_roles["roles"])
            for k in sortorder:
                roles.move_to_end(k)
            msg = "Role → Level\n"
            for role in roles:
                if roles[role]["remove_role"]:
                    msg += "• {} → {} (Removes: {})\n".format(
                        role, roles[role]["level"], roles[role]["remove_role"]
                    )
                else:
                    msg += "• {} → {}\n".format(role, roles[role]["level"])

        pages = list(chat.pagify(msg, page_length=2048))
        embeds = []
        # TODO: Use dpy menus
        for i, page in enumerate(pages, start=1):
            em = discord.Embed(description=page, colour=await ctx.embed_color())
            em.set_author(
                name="Current Role - Level Links for {}".format(server.name),
                icon_url=server.icon_url,
            )
            em.set_footer(text=f"Page {i}/{len(pages)}")
            embeds.append(em)
        await menu(ctx, embeds, DEFAULT_CONTROLS)
