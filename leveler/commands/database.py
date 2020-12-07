import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting as chat
from tabulate import tabulate

from ..abc import CompositeMetaClass, MixinMeta

concurrency = commands.MaxConcurrency(1, per=commands.BucketType.default, wait=False)


def levelerset_concurrency():
    """Custom concurrency pool for levelerset commands"""

    def decorator(func):
        if isinstance(func, commands.Command):
            func._max_concurrency = concurrency
        else:
            func.__commands_max_concurrency__ = concurrency
        return func

    return decorator


class DataBase(MixinMeta, metaclass=CompositeMetaClass):
    @commands.is_owner()
    @commands.group()
    async def levelerset(self, ctx):
        """
        MongoDB server configuration options.

        Use that command in DM to see current settings.
        """
        if not ctx.invoked_subcommand and ctx.channel.type == discord.ChannelType.private:
            settings = [
                (setting.replace("_", " ").title(), value)
                for setting, value in (await self.config.custom("MONGODB").get_raw()).items()
                if value
            ]
            await ctx.send(chat.box(tabulate(settings, tablefmt="plain")))

    @levelerset.command()
    @levelerset_concurrency()
    async def host(self, ctx, host: str = "localhost"):
        """Set the MongoDB server host."""
        await self.config.custom("MONGODB").host.set(host)
        message = await ctx.send(
            f"MongoDB host set to {host}.\nNow trying to connect to the new host..."
        )
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect to the new host...", "")
                + "Failed to connect. Please try again with a valid host."
            )
        await message.edit(
            content=message.content.replace("Now trying to connect to the new host...", "")
        )

    @levelerset.command()
    @levelerset_concurrency()
    async def port(self, ctx, port: int = 27017):
        """Set the MongoDB server port."""
        await self.config.custom("MONGODB").port.set(port)
        message = await ctx.send(
            f"MongoDB port set to {port}.\nNow trying to connect to the new port..."
        )
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect to the new port...", "")
                + "Failed to connect. Please try again with a valid port."
            )
        await message.edit(
            content=message.content.replace("Now trying to connect to the new port...", "")
        )

    @levelerset.command(aliases=["creds"])
    @levelerset_concurrency()
    async def credentials(self, ctx, username: str = None, password: str = None):
        """Set the MongoDB server credentials."""
        await self.config.custom("MONGODB").username.set(username)
        await self.config.custom("MONGODB").password.set(password)
        message = await ctx.send("MongoDB credentials set.\nNow trying to connect...")
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect...", "")
                + "Failed to connect. Please try again with valid credentials."
            )
        await message.edit(content=message.content.replace("Now trying to connect...", ""))

    @levelerset.command()
    @levelerset_concurrency()
    async def dbname(self, ctx, dbname: str = "leveler"):
        """Set the MongoDB db name."""
        await self.config.custom("MONGODB").db_name.set(dbname)
        message = await ctx.send("MongoDB db name set.\nNow trying to connect...")
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect...", "")
                + "Failed to connect. Please try again with a valid db name."
            )
        await message.edit(content=message.content.replace("Now trying to connect...", ""))
