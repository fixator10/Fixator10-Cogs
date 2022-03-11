from redbot.core import bank, commands

from leveler.abc import MixinMeta

from .basecmd import LevelAdminBaseCMD


# noinspection PyUnusedLocal
async def non_global_bank(ctx):
    return not await bank.is_global()


# noinspection PyUnusedLocal
async def global_bank(ctx):
    return await bank.is_global()


class Economy(MixinMeta):
    """Economy administration commands"""

    lvladmin = getattr(LevelAdminBaseCMD, "lvladmin")

    @lvladmin.command()
    @commands.guild_only()
    @commands.check(non_global_bank)
    async def msgcredits(self, ctx, currency: int = 0):
        """Credits per message logged.

        Default to `0`."""
        server = ctx.guild

        if currency < 0 or currency > 1000:
            await ctx.send("Please enter a valid number between 0 and 1000.")
            return

        await self.config.guild(server).msg_credits.set(currency)
        await ctx.send("Credits per message logged set to `{}`.".format(currency))

    @commands.is_owner()
    @lvladmin.command()
    @commands.check(global_bank)
    @commands.guild_only()
    async def setprice(self, ctx, price: int):
        """Set a price for background changes."""
        if price < 0:
            await ctx.send("That is not a valid background price.")
        else:
            await self.config.bg_price.set(price)
            await ctx.send(f"Background price set to: `{price}`!")
