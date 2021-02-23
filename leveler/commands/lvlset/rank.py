import random
from sys import modules
from typing import Union

import discord
from redbot.core import commands

from leveler.abc import MixinMeta

from .basecmd import LevelSetBaseCMD


class Rank(MixinMeta):
    """Rank commands"""

    lvlset = getattr(LevelSetBaseCMD, "lvlset")

    @lvlset.group(name="rank", pass_context=True)
    async def rankset(self, ctx):
        """Rank options."""

    @rankset.command(name="color", alias=["colour"])
    @commands.guild_only()
    async def rankcolors(self, ctx, section: str, color: Union[discord.Color, str]):
        """Set rank color.

        For section, you can choose: `exp`, `info` or `all`.
        For color, you can use: `default`, `white`, `HEX code` (#000000) or `auto`.
        e.g: `[p]lvlset rank color info white`"""
        user = ctx.author
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_exp = (255, 255, 255, 230)
        default_rep = (92, 130, 203, 230)
        default_badge = (128, 151, 165, 230)
        default_a = 200

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("Text-only commands allowed.")
            return

        # get correct section for db query
        if section == "exp":
            section_name = "rank_exp_color"
        elif section == "info":
            section_name = "rank_info_color"
        elif section == "all":
            section_name = "all"
        else:
            await ctx.send("Not a valid section. Must be `exp`, `info` or `all`")
            return

        # get correct color choice
        if color == "auto":
            if not all(module in modules for module in ("numpy", "scipy.cluster")):
                await ctx.send("Missing required package. Autocolor feature unavailable")
                return
            if section == "exp":
                color_ranks = [random.randint(2, 3)]
            elif section == "info":
                color_ranks = [random.randint(0, 1)]
            elif section == "all":
                color_ranks = [random.randint(2, 3), random.randint(0, 1)]

            hex_colors = await self._auto_color(ctx, userinfo["rank_background"], color_ranks)
            if section == "all":
                set_color = [await self._hex_to_rgb(color, default_a) for color in hex_colors]
            else:
                set_color = hex_colors[0]
        elif color == "white":
            set_color = white_info_color
        elif color == "default":
            if section == "exp":
                set_color = default_exp
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
            await ctx.send("Not a valid color. Must be `default`, `HEX color`, `white or `auto`.")
            return

        if section == "all":
            if isinstance(color, discord.Color):
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "rank_exp_color": set_color,
                            "rank_info_color": set_color,
                        }
                    },
                )
            elif color == "default":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "rank_exp_color": default_exp,
                            "rank_info_color": default_info_color,
                        }
                    },
                )
            elif color == "auto":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "rank_exp_color": set_color[0],
                            "rank_info_color": set_color[1],
                        }
                    },
                )
            await ctx.send("Colors for rank set.")
        else:
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {section_name: set_color}}
            )
            await ctx.send("Color for rank {} set.".format(section))

    @rankset.command(name="bg")
    @commands.guild_only()
    async def rankbg(self, ctx, *, image_name: str):
        """Set your rank background."""
        user = ctx.author
        backgrounds = await self.config.backgrounds()

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("Text-only commands allowed.")
            return

        if image_name in backgrounds["rank"].keys():
            if await self._process_purchase(ctx):
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"rank_background": backgrounds["rank"][image_name]}},
                )
                await ctx.send("Your new rank background has been succesfully set!")
        else:
            await ctx.send(
                f"That is not a valid background. See available backgrounds at `{ctx.clean_prefix}backgrounds rank`."
            )
