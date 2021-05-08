from collections import OrderedDict
from typing import Optional

import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from leveler.abc import MixinMeta

from .basecmd import LevelAdminBaseCMD


class Badge(MixinMeta):
    """Badge administration commands"""

    lvladmin = getattr(LevelAdminBaseCMD, "lvladmin")

    @lvladmin.group()
    async def badge(self, ctx):
        """Badge Configuration Options."""

    @commands.mod_or_permissions(manage_roles=True)
    @badge.command(name="add")
    @commands.guild_only()
    async def addbadge(
        self,
        ctx,
        name: str,
        is_global: Optional[bool],
        bg_img: str,
        border_color: discord.Color,
        price: int,
        *,
        description: str,
    ):
        """Add a badge.

        Options:
        `name`: Indicate badge's name. If the badge has space, use quote.
        `is_global`: Owner-only. Make badge global.
        `bg_img`: Indicate the image of the badge. (Only URL supported)
        `border_color`: Indicate color of the badge's border. (HEX color)
        `price`: Indicate the badge's price. (Indicate `-1` and it won't be purchasable, `0` for free.)
        `description`: Indicate a description for your badge."""

        user = ctx.author
        server = ctx.guild

        # check members
        required_members = 35
        members = len([member for member in server.members if not member.bot])

        if await self.bot.is_owner(user):
            pass
        elif members < required_members:
            await ctx.send(
                "You may only add badges in servers with {}+ non-bot members".format(
                    required_members
                )
            )
            return

        if is_global and await self.bot.is_owner(user):
            serverid = "global"
            servername = "global"
        else:
            serverid = server.id
            servername = server.name

        if "." in name:
            await ctx.send("Name cannot contain `.`")
            return

        if not await self._valid_image_url(bg_img):
            await ctx.send("Background is not valid. Enter HEX color or image URL!")
            return

        if price < -1:
            await ctx.send("Price is not valid!")
            return

        if len(description.split(" ")) > 40:
            await ctx.send("Description is too long! Must be 40 or less.")
            return

        badges = await self.db.badges.find_one({"server_id": str(serverid)})
        if not badges:
            await self.db.badges.insert_one({"server_id": str(serverid), "badges": {}})
            badges = await self.db.badges.find_one({"server_id": str(serverid)})

        new_badge = {
            "badge_name": name,
            "bg_img": bg_img,
            "price": price,
            "description": description,
            "border_color": str(border_color),
            "server_id": str(serverid),
            "server_name": servername,
            "priority_num": 0,
        }

        if name not in badges["badges"].keys():
            # create the badge regardless
            badges["badges"][name] = new_badge
            await self.db.badges.update_one(
                {"server_id": str(serverid)}, {"$set": {"badges": badges["badges"]}}
            )
            await ctx.send("`{}` Badge added in `{}` server.".format(name, servername))
        else:
            # update badge in the server
            badges["badges"][name] = new_badge
            await self.db.badges.update_one(
                {"server_id": str(serverid)}, {"$set": {"badges": badges["badges"]}}
            )

            # go though all users and update the badge.
            # Doing it this way because dynamic does more accesses when doing profile
            async for user in self.db.users.find({}):
                try:
                    user = await self._badge_convert_dict(user)
                    userbadges = user["badges"]
                    badge_name = "{}_{}".format(name, serverid)
                    if badge_name in userbadges.keys():
                        user_priority_num = userbadges[badge_name]["priority_num"]
                        new_badge[
                            "priority_num"
                        ] = user_priority_num  # maintain old priority number set by user
                        userbadges[badge_name] = new_badge
                        await self.db.users.update_one(
                            {"user_id": user["user_id"]},
                            {"$set": {"badges": userbadges}},
                        )
                except Exception as exc:
                    self.log.error(
                        f"Unable to update badge {name} for {user['user_id']}", exc_info=exc
                    )
            await ctx.send("The `{}` badge has been updated".format(name))

    @commands.is_owner()
    @badge.command()
    @commands.guild_only()
    async def type(self, ctx, name: str):
        """Define if badge must be circles or bars."""
        valid_types = ["circles", "bars"]
        if name.lower() not in valid_types:
            await ctx.send("That is not a valid badge type!")
            return

        await self.config.badge_type.set(name.lower())
        await ctx.send("Badge type set to `{}`".format(name.lower()))

    @commands.mod_or_permissions(manage_roles=True)
    @badge.command(name="delete")
    @commands.guild_only()
    async def delbadge(self, ctx, is_global: Optional[bool] = False, *, name: str):
        """Delete a badge and remove from all users."""
        user = ctx.author
        server = ctx.guild

        if is_global and await self.bot.is_owner(user):
            serverid = "global"
        else:
            serverid = server.id

        serverbadges = await self.db.badges.find_one({"server_id": str(serverid)})
        if serverbadges and name in serverbadges["badges"].keys():
            del serverbadges["badges"][name]
            await self.db.badges.update_one(
                {"server_id": serverbadges["server_id"]},
                {"$set": {"badges": serverbadges["badges"]}},
            )
            # remove the badge if there
            async with ctx.typing():
                async for user_info_temp in self.db.users.find({}):
                    try:
                        user_info_temp = await self._badge_convert_dict(user_info_temp)

                        badge_name = "{}_{}".format(name, serverid)
                        if badge_name in user_info_temp["badges"].keys():
                            del user_info_temp["badges"][badge_name]
                            await self.db.users.update_one(
                                {"user_id": user_info_temp["user_id"]},
                                {"$set": {"badges": user_info_temp["badges"]}},
                            )
                    except Exception as exc:
                        self.log.error(
                            f"Unable to delete badge {name} from {user_info_temp['user_id']}",
                            exc_info=exc,
                        )

            await ctx.send("The `{}` badge has been removed.".format(name))
        else:
            await ctx.send("That badge does not exist.")

    @commands.mod_or_permissions(manage_roles=True)
    @badge.command()
    @commands.guild_only()
    async def give(self, ctx, user: discord.Member, is_global: Optional[bool], name: str):
        """Give a user a badge by its name.

        Options:
        `user`: User to get a badge
        `is_global`: Owner-only. Give global badge.
        `name`: Badge name."""
        org_user = ctx.message.author
        server_id = (
            "global" if is_global and await self.bot.is_owner(org_user) else str(ctx.guild.id)
        )
        if user.bot:
            await ctx.send_help()
            return
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        serverbadges = await self.db.badges.find_one({"server_id": server_id})
        badge_name = "{}_{}".format(name, server_id)

        if not serverbadges or name not in (badges := serverbadges["badges"]):
            await ctx.send("That badge doesn't exist in this server!")
            return
        if badge_name in badges.keys():
            await ctx.send(
                "{} already has that badge!".format(user.mention),
                allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
            )
            return
        userinfo["badges"][badge_name] = badges[name]
        await self.db.users.update_one(
            {"user_id": str(user.id)}, {"$set": {"badges": userinfo["badges"]}}
        )
        await ctx.send(
            "{} has just given {} the `{}` badge!".format(org_user.mention, user.mention, name),
            allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
        )

    @commands.mod_or_permissions(manage_roles=True)
    @badge.command()
    @commands.guild_only()
    async def take(self, ctx, user: discord.Member, name: str):
        """Take a user's badge.

        Indicate the user and the badge's name."""
        if user.bot:
            await ctx.send_help()
            return
        org_user = ctx.author
        server = ctx.guild
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        serverbadges = await self.db.badges.find_one({"server_id": str(server.id)})
        badge_name = "{}_{}".format(name, server.id)

        if not serverbadges or name not in serverbadges["badges"]:
            await ctx.send("That badge doesn't exist in this server!")
        elif badge_name not in userinfo["badges"]:
            await ctx.send(
                "{} does not have that badge!".format(user.mention),
                allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
            )
        else:
            if userinfo["badges"][badge_name]["price"] == -1:
                del userinfo["badges"][badge_name]
                await self.db.users.update_one(
                    {"user_id": str(user.id)}, {"$set": {"badges": userinfo["badges"]}}
                )
                await ctx.send(
                    "{} has taken the `{}` badge from {}! :upside_down:".format(
                        org_user.mention,
                        name,
                        user.mention,
                    ),
                    allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
                )
            else:
                await ctx.send("You can't take away purchasable badges!")

    @commands.mod_or_permissions(manage_roles=True)
    @badge.command(name="link")
    @commands.guild_only()
    async def linkbadge(self, ctx, badge_name: str, level: int):
        """Associate a badge with a level.

        Indicate the badge's name and the level."""
        server = ctx.guild
        serverbadges = await self.db.badges.find_one({"server_id": str(server.id)})

        if not serverbadges or badge_name not in serverbadges["badges"]:
            await ctx.send("Please make sure the `{}` badge exists!".format(badge_name))
            return
        server_linked_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})
        if not server_linked_badges:
            new_server = {
                "server_id": str(server.id),
                "badges": {badge_name: str(level)},
            }
            await self.db.badgelinks.insert_one(new_server)
        else:
            server_linked_badges["badges"][badge_name] = str(level)
            await self.db.badgelinks.update_one(
                {"server_id": str(server.id)},
                {"$set": {"badges": server_linked_badges["badges"]}},
            )
        await ctx.send("The `{}` badge has been linked to level `{}`".format(badge_name, level))

    @commands.admin_or_permissions(manage_roles=True)
    @badge.command(name="unlink")
    @commands.guild_only()
    async def unlinkbadge(self, ctx, badge_name: str):
        """Delete a badge/level association."""
        server = ctx.guild

        server_linked_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})

        if server_linked_badges and badge_name in (
            badge_links := server_linked_badges["badges"].keys()
        ):
            del badge_links[badge_name]
            await self.db.badgelinks.update_one(
                {"server_id": str(server.id)}, {"$set": {"badges": badge_links}}
            )
            await ctx.send(
                "Badge/Level association `{}`/`{}` removed.".format(
                    badge_name, badge_links[badge_name]
                )
            )
        else:
            await ctx.send("The `{}` badge is not linked to any levels!".format(badge_name))

    @commands.mod_or_permissions(manage_roles=True)
    @badge.command(name="listlinks")
    @commands.guild_only()
    async def listbadge(self, ctx):
        """List level/badge associations."""
        server = ctx.guild

        server_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})

        if server_badges is None or not server_badges.get("badges"):
            msg = "None"
        else:
            sortorder = sorted(
                server_badges["badges"], key=lambda b: int(server_badges["badges"][b])
            )
            badges = OrderedDict(server_badges["badges"])
            for k in sortorder:
                badges.move_to_end(k)
            msg = "Badge → Level\n"
            for badge in badges.keys():
                msg += "• {} → {}\n".format(badge, badges[badge])

        pages = list(chat.pagify(msg, page_length=2048))
        embeds = []
        # TODO: Use dpy menus
        for i, page in enumerate(pages, start=1):
            em = discord.Embed(description=page, colour=await ctx.embed_color())
            em.set_author(
                name="Current Badge - Level Links for {}".format(server.name),
                icon_url=server.icon_url,
            )
            em.set_footer(text=f"Page {i}/{len(pages)}")
            embeds.append(em)
        await menu(ctx, embeds, DEFAULT_CONTROLS)
