import random
from sys import modules
from typing import Union

import discord
from redbot.core import commands

from leveler.abc import MixinMeta

from .basecmd import LevelSetBaseCMD


class Levelup(MixinMeta):
    """Levelup commands"""

    lvlset = getattr(LevelSetBaseCMD, "lvlset")

    @lvlset.group(name="levelup", pass_context=True)
    async def levelupset(self, ctx):
        """Level-Up options."""
        pass

    @levelupset.command(name="color", alias=["colour"])
    @commands.guild_only()
    async def levelupcolors(self, ctx, section: str, color: Union[discord.Color, str]):
        """Set levelup color.

        Section can only be `info`.
        Color can be : `default`, `HEX code` (#000000) or `auto`.
        e.g: `[p]lvlset color info default`"""
        user = ctx.author
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        default_a = 200

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("Text-only commands allowed.")
            return

        # get correct section for db query
        if section == "info":
            section_name = "levelup_info_color"
        else:
            await ctx.send("Not a valid section. Must be `info`.")
            return

        # get correct color choice
        if color == "auto":
            if not all(module in modules for module in ("numpy", "scipy.cluster")):
                await ctx.send("Missing required package. Autocolor feature unavailable")
                return
            if section == "info":
                color_ranks = [random.randint(0, 1)]
            hex_colors = await self._auto_color(ctx, userinfo["levelup_background"], color_ranks)
            set_color = hex_colors[0]
        elif color == "default":
            if section == "info":
                set_color = default_info_color
        elif isinstance(color, discord.Color):
            set_color = (color.r, color.g, color.b, default_a)
        else:
            await ctx.send("Not a valid color. Must be `default` `HEX color` or `auto`.")
            return

        await self.db.users.update_one(
            {"user_id": str(user.id)}, {"$set": {section_name: set_color}}
        )
        await ctx.send("Color for level-up {} set.".format(section))

    @levelupset.command(name="bg")
    @commands.guild_only()
    async def levelbg(self, ctx, *, image_name: str):
        """Set your level-up background."""
        user = ctx.author
        backgrounds = await self.config.backgrounds()

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("Text-only commands allowed.")
            return

        if image_name in backgrounds["levelup"].keys():
            if await self._process_purchase(ctx):
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"levelup_background": backgrounds["levelup"][image_name]}},
                )
                await ctx.send("Your new level-up background has been succesfully set!")
        else:
            await ctx.send(
                f"That is not a valid background. See available backgrounds at `{ctx.clean_prefix}backgrounds levelup`."
            )
