import random
from sys import modules
from typing import Union

import discord
from redbot.core import commands

from leveler.abc import MixinMeta

from .basecmd import LevelSetBaseCMD


class Profile(MixinMeta):
    """Profile commands"""

    lvlset = getattr(LevelSetBaseCMD, "lvlset")

    @lvlset.group(name="profile")
    async def profileset(self, ctx):
        """Profile options."""

    @profileset.command(name="color", alias=["colour"])
    @commands.guild_only()
    async def profilecolors(self, ctx, section: str, color: Union[discord.Color, str]):
        """Set profile color.

        For section, you can choose: `exp`, `rep`, `badge`, `info` or `all`.
        For color, you can use: `default`, `white`, `HEX code` (#000000) or `auto`.
        e.g: `[p]lvlset profile color all #eb4034`"""
        user = ctx.author
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        default_rep = (92, 130, 203, 230)
        default_badge = (128, 151, 165, 230)
        default_exp = (255, 255, 255, 230)
        default_a = 200

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("Text-only commands allowed.")
            return

        # get correct section for db query
        if section == "rep":
            section_name = "rep_color"
        elif section == "exp":
            section_name = "profile_exp_color"
        elif section == "badge":
            section_name = "badge_col_color"
        elif section == "info":
            section_name = "profile_info_color"
        elif section == "all":
            section_name = "all"
        else:
            await ctx.send("Not a valid section. Must be `rep`, `exp`, `badge`, `info` or `all`.")
            return

        # get correct color choice
        if color == "auto":
            if not all(module in modules for module in ("numpy", "scipy.cluster")):
                await ctx.send("Missing required package. Autocolor feature unavailable")
                return
            if section == "exp":
                color_ranks = [random.randint(2, 3)]
            elif section == "rep":
                color_ranks = [random.randint(2, 3)]
            elif section == "badge":
                color_ranks = [0]  # most prominent color
            elif section == "info":
                color_ranks = [random.randint(0, 1)]
            elif section == "all":
                color_ranks = [
                    random.randint(2, 3),
                    random.randint(2, 3),
                    0,
                    random.randint(0, 2),
                ]

            hex_colors = await self._auto_color(ctx, userinfo["profile_background"], color_ranks)
            if section == "all":
                set_color = [await self._hex_to_rgb(color, default_a) for color in hex_colors]
            else:
                set_color = hex_colors[0]
        elif color == "default":
            if section == "exp":
                set_color = default_exp
            elif section == "rep":
                set_color = default_rep
            elif section == "badge":
                set_color = default_badge
            elif section == "info":
                set_color = default_info_color
            elif section == "all":
                set_color = [
                    default_exp,
                    default_rep,
                    default_badge,
                    default_info_color,
                ]
        elif isinstance(color, discord.Color):
            set_color = (color.r, color.g, color.b, default_a)
        else:
            await ctx.send("Not a valid color. Must be `default`, `HEX color` or `auto`.")
            return

        if section == "all":
            if isinstance(color, discord.Color):
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_exp_color": set_color,
                            "rep_color": set_color,
                            "badge_col_color": set_color,
                            "profile_info_color": set_color,
                        }
                    },
                )
            elif color == "default":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_exp_color": default_exp,
                            "rep_color": default_rep,
                            "badge_col_color": default_badge,
                            "profile_info_color": default_info_color,
                        }
                    },
                )
            elif color == "auto":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_exp_color": set_color[0],
                            "rep_color": set_color[1],
                            "badge_col_color": set_color[2],
                            "profile_info_color": set_color[3],
                        }
                    },
                )
            await ctx.send("Colors for profile set.")
        else:
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {section_name: set_color}}
            )
            await ctx.send("Color for profile {} set.".format(section))

    @profileset.command(name="bg")
    @commands.guild_only()
    async def profilebg(self, ctx, *, image_name: str):
        """Set your profile background."""
        user = ctx.author
        backgrounds = await self.config.backgrounds()

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("Text-only commands allowed.")
            return

        if image_name in backgrounds["profile"].keys():
            if await self._process_purchase(ctx):
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"profile_background": backgrounds["profile"][image_name]}},
                )
                await ctx.send("Your new profile background has been succesfully set!")
        else:
            await ctx.send(
                f"That is not a valid background. See available backgrounds at `{ctx.clean_prefix}backgrounds profile`."
            )

    @profileset.command()
    @commands.guild_only()
    async def title(self, ctx, *, title):
        """Set your title."""
        user = ctx.author
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        max_char = 20

        if len(title) < max_char:
            userinfo["title"] = title
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"title": title}})
            await ctx.send("Your title has been succesfully set!")
        else:
            await ctx.send(
                "Your title has too many characters! Must be {} or less.".format(max_char)
            )

    @profileset.command()
    @commands.guild_only()
    async def info(self, ctx, *, info):
        """Set your user info."""
        user = ctx.author
        max_char = 150

        if len(info) < max_char:
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"info": info}})
            await ctx.send("Your info section has been succesfully set!")
        else:
            await ctx.send(
                "Your description has too many characters! Must be {} or less.".format(max_char)
            )
