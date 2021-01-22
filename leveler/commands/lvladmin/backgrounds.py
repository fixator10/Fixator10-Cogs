from redbot.core import commands

from leveler.abc import MixinMeta

from .basecmd import LevelAdminBaseCMD


class Backgrounds(MixinMeta):
    """Backgrounds administration commands"""

    lvladmin = getattr(LevelAdminBaseCMD, "lvladmin")

    @lvladmin.group(name="bg")
    @commands.is_owner()
    @commands.guild_only()
    async def lvladminbg(self, ctx):
        """Admin background configuration"""
        pass

    @lvladminbg.command()
    async def addprofilebg(self, ctx, name: str, url: str):
        """Add a profile background.

        The proportions must be 290px x 290px."""
        backgrounds = await self.config.backgrounds()
        if name in backgrounds["profile"].keys():
            await ctx.send("That profile background name already exists!")
        elif not await self._valid_image_url(url):
            await ctx.send("That is not a valid image URL!")
        else:
            async with self.config.backgrounds() as backgrounds:
                backgrounds["profile"][name] = url
            await ctx.send("New profile background (`{}`) added.".format(name))

    @lvladminbg.command()
    async def addrankbg(self, ctx, name: str, url: str):
        """Add a rank background.

        The proportions must be 360px x 100px."""
        backgrounds = await self.config.backgrounds()
        if name in backgrounds["profile"].keys():
            await ctx.send("That rank background name already exists!")
        elif not await self._valid_image_url(url):
            await ctx.send("That is not a valid image URL!")
        else:
            async with self.config.backgrounds() as backgrounds:
                backgrounds["rank"][name] = url
            await ctx.send("New rank background (`{}`) added.".format(name))

    @lvladminbg.command()
    async def addlevelbg(self, ctx, name: str, url: str):
        """Add a level-up background.

        The proportions must be 175px x 65px."""
        backgrounds = await self.config.backgrounds()
        if name in backgrounds["levelup"].keys():
            await ctx.send("That level-up background name already exists!")
        elif not await self._valid_image_url(url):
            await ctx.send("That is not a valid image URL!")
        else:
            async with self.config.backgrounds() as backgrounds:
                backgrounds["levelup"][name] = url
            await ctx.send("New level-up background (`{}`) added.".format(name))

    @lvladminbg.command()
    async def setcustombg(self, ctx, bg_type: str, user_id: str, img_url: str):
        """Set one-time custom background

        bg_type can be: `profile`, `rank` or `levelup`."""
        valid_types = ["profile", "rank", "levelup"]
        type_input = bg_type.lower()

        if type_input not in valid_types:
            await ctx.send("Please choose a valid type. Must be `profile`, `rank` or `levelup`.")
            return

        # test if valid user_id
        userinfo = await self.db.users.find_one({"user_id": str(user_id)})
        if not userinfo:
            await ctx.send("That is not a valid user id!")
            return

        if not await self._valid_image_url(img_url):
            await ctx.send("That is not a valid image URL!")
            return

        await self.db.users.update_one(
            {"user_id": str(user_id)},
            {"$set": {"{}_background".format(type_input): img_url}},
        )
        await ctx.send("User {} custom {} background set.".format(user_id, bg_type))

    @lvladminbg.command()
    async def delprofilebg(self, ctx, name: str):
        """Delete a profile background."""
        bgs = await self.config.backgrounds()
        if name in bgs["profile"].keys():
            await self.config.clear_raw("backgrounds", "profile", name)
            await ctx.send("The profile background(`{}`) has been deleted.".format(name))
        else:
            await ctx.send("That profile background name doesn't exist.")

    @lvladminbg.command()
    async def delrankbg(self, ctx, name: str):
        """Delete a rank background."""
        bgs = await self.config.backgrounds()
        if name in bgs["rank"].keys():
            await self.config.clear_raw("backgrounds", "rank", name)
            await ctx.send("The rank background(`{}`) has been deleted.".format(name))
        else:
            await ctx.send("That rank background name doesn't exist.")

    @lvladminbg.command()
    async def dellevelbg(self, ctx, name: str):
        """Delete a level background."""
        bgs = await self.config.backgrounds()
        if name in bgs["levelup"].keys():
            await self.config.clear_raw("backgrounds", "levelup", name)
            await ctx.send("The level-up background(`{}`) has been deleted.".format(name))
        else:
            await ctx.send("That level-up background name doesn't exist.")
