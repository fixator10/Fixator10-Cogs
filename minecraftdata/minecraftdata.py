import base64
import io
import re
from base64 import b64decode
from datetime import datetime
from io import BytesIO

import aiohttp
import discord
import tabulate
from mcstatus import MinecraftServer
from redbot.core import checks
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from .minecraftplayer import MCPlayer

_ = Translator("MinecraftData", __file__)

SERVICE_STATUS = {
    "red": _("💔 **UNAVAILABLE**"),
    "yellow": _("💛 **SOME ISSUES**"),
    "green": _("💚 **OK**"),
}


@cog_i18n(_)
class MinecraftData(commands.Cog):
    """Minecraft-Related data"""

    # noinspection PyMissingConstructor
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.group(aliases=["mc"])
    async def minecraft(self, ctx):
        """Get Minecraft-Related data"""
        pass

    @minecraft.command(usage="<player> [overlay layer=True]")
    @checks.bot_has_permissions(embed_links=True)
    async def skin(self, ctx, player: MCPlayer, overlay: bool = True):
        """Get minecraft skin by nickname"""
        uuid = player.uuid
        stripname = player.name.strip("_")
        files = []
        async with ctx.channel.typing():
            try:
                async with self.session.get(
                        f"https://crafatar.com/renders/head/{uuid}",
                        params="overlay" if overlay else None,
                ) as s:
                    files.append(
                        discord.File(
                            BytesIO(await s.read()), filename=f"{stripname}_head.png"
                        )
                    )
                async with self.session.get(f"https://crafatar.com/skins/{uuid}") as s:
                    files.append(
                        discord.File(
                            BytesIO(await s.read()), filename=f"{stripname}.png"
                        )
                    )
                async with self.session.get(
                        f"https://crafatar.com/renders/body/{uuid}.png",
                        params="overlay" if overlay else None,
                ) as s:
                    files.append(
                        discord.File(
                            BytesIO(await s.read()), filename=f"{stripname}_body.png"
                        )
                    )
            except aiohttp.ClientResponseError as e:
                await ctx.send(
                    chat.error(
                        _("Unable to get data from Crafatar: {}").format(e.message)
                    )
                )
                return
        em = discord.Embed(
            timestamp=ctx.message.created_at, color=await ctx.embed_color()
        )
        em.set_author(
            name=player.name,
            icon_url=f"attachment://{stripname}_head.png",
            url=f"https://crafatar.com/skins/{uuid}",
        )
        em.set_thumbnail(url=f"attachment://{stripname}.png")
        em.set_image(url=f"attachment://{stripname}_body.png")
        em.set_footer(
            text=_("Provided by Crafatar"), icon_url="https://crafatar.com/logo.png"
        )
        await ctx.send(embed=em, files=files)

    @minecraft.group(invoke_without_command=True)
    @checks.bot_has_permissions(embed_links=True)
    async def cape(self, ctx, player: MCPlayer):
        """Get minecraft capes by nickname"""
        try:
            await self.session.get(
                f"https://crafatar.com/capes/{player.uuid}", raise_for_status=True
            )
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                await ctx.send(
                    chat.error(_("{} doesn't have cape").format(player.name))
                )
            else:
                await ctx.send(
                    chat.error(_("Unable to get cape: {}").format(e.message))
                )
            return
        em = discord.Embed(
            timestamp=ctx.message.created_at, color=await ctx.embed_color()
        )
        em.set_author(name=player.name, url=f"https://crafatar.com/capes/{player.uuid}")
        em.set_image(url=f"https://crafatar.com/capes/{player.uuid}")
        await ctx.send(embed=em)

    @cape.command(aliases=["of"])
    async def optifine(self, ctx, player: MCPlayer):
        """Get optifine cape by nickname"""
        try:
            await self.session.get(
                f"http://s.optifine.net/capes/{player.name}.png", raise_for_status=True
            )
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                await ctx.send(
                    chat.error(_("{} doesn't have optifine cape").format(player.name))
                )
            else:
                await ctx.send(
                    chat.error(
                        _("Unable to get {player}'s optifine cape: {message}").format(
                            player=player.name, message=e.message
                        )
                    )
                )
            return
        em = discord.Embed(
            timestamp=ctx.message.created_at, color=await ctx.embed_color()
        )
        em.set_author(
            name=player.name, url=f"http://s.optifine.net/capes/{player.name}.png"
        )
        em.set_image(url=f"http://s.optifine.net/capes/{player.name}.png")
        await ctx.send(embed=em)

    @cape.command()
    async def labymod(self, ctx, player: MCPlayer):
        """Get LabyMod cape by nickname"""
        uuid = player.dashed_uuid
        try:
            async with self.session.get(
                    f"http://capes.labymod.net/capes/{uuid}", raise_for_status=True
            ) as data:
                cape = await data.read()
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                await ctx.send(
                    chat.error(_("{} doesn't have LabyMod cape").format(player.name))
                )
            else:
                await ctx.send(
                    chat.error(
                        _("Unable to get data: {message} ({status})").format(
                            status=e.status, message=e.message
                        )
                    )
                )
            return
        cape = io.BytesIO(cape)
        file = discord.File(cape, filename="{}.png".format(player))
        await ctx.send(file=file)
        cape.close()

    @cape.command(aliases=["minecraftcapes", "couk"])
    async def mccapes(self, ctx, player: MCPlayer):
        """Get MinecraftCapes.co.uk cape by nickname"""
        try:
            await self.session.get(
                f"https://www.minecraftcapes.co.uk/getCape.php?uuid={player.uuid}",
                raise_for_status=True,
            )
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                await ctx.send(
                    chat.error(
                        _("{} doesn't have MinecraftCapes cape").format(player.name)
                    )
                )
            else:
                await ctx.send(
                    chat.error(
                        _(
                            "Unable to get {player}'s MinecraftCapes cape: {message}"
                        ).format(player=player.name, message=e.message)
                    )
                )
            return
        em = discord.Embed(
            timestamp=ctx.message.created_at, color=await ctx.embed_color()
        )
        em.set_author(
            name=player.name,
            url=f"https://www.minecraftcapes.co.uk/getCape.php?uuid={player.uuid}",
        )
        em.set_image(
            url=f"https://www.minecraftcapes.co.uk/getCape.php?uuid={player.uuid}"
        )
        await ctx.send(embed=em)

    @cape.group(aliases=["5zig"], invoke_without_command=True)
    async def fivezig(self, ctx, player: MCPlayer):
        """Get 5zig cape by nickname"""
        uuid = player.uuid
        try:
            async with self.session.get(
                    f"http://textures.5zig.net/textures/2/{uuid}", raise_for_status=True
            ) as data:
                response_data = await data.json(content_type=None)
            cape = response_data["cape"]
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                await ctx.send(
                    chat.error(_("{} doesn't have 5zig cape").format(player.name))
                )
            else:
                await ctx.send(
                    chat.error(
                        _("Unable to get {player}'s 5zig cape: {message}").format(
                            player=player.name, message=e.message
                        )
                    )
                )
            return
        cape = io.BytesIO(base64.decodebytes(cape.encode()))
        file = discord.File(cape, filename="{}.png".format(player))
        await ctx.send(file=file)
        cape.close()

    @fivezig.command(name="animated")
    async def fivezig_animated(self, ctx, player: MCPlayer):
        """Get 5zig animated cape by nickname"""
        uuid = player.uuid
        try:
            async with self.session.get(
                    f"http://textures.5zig.net/textures/2/{uuid}", raise_for_status=True
            ) as data:
                response_data = await data.json(content_type=None)
            if "animatedCape" not in response_data:
                await ctx.send(
                    chat.error(_("{} doesn't have animated 5zig cape")).format(
                        player.name
                    )
                )
                return
            cape = response_data["animatedCape"]
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                await ctx.send(
                    chat.error(_("{} doesn't have 5zig cape").format(player.name))
                )
            else:
                await ctx.send(
                    chat.error(
                        _("Unable to get {player}'s 5zig cape: {message}").format(
                            player=player.name, message=e.message
                        )
                    )
                )
            return
        cape = io.BytesIO(base64.decodebytes(cape.encode()))
        file = discord.File(cape, filename="{}.png".format(player))
        await ctx.send(file=file)
        cape.close()

    @minecraft.command(usage="<server IP>")
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def server(self, ctx, server_ip: str):
        """Get info about server"""
        try:
            server = await self.bot.loop.run_in_executor(
                None, MinecraftServer.lookup, server_ip
            )
        except Exception as e:
            await ctx.send(chat.error(_("Unable to resolve IP: {}").format(e)))
            return
        async with ctx.channel.typing():
            try:
                status = await self.bot.loop.run_in_executor(None, server.status)
            except OSError as e:
                await ctx.send(
                    chat.error(_("Unable to get server's status: {}").format(e))
                )
                return
            try:
                query = await self.bot.loop.run_in_executor(None, server.query)
            except (ConnectionResetError, OSError):
                query = None
        icon = (
            discord.File(
                BytesIO(b64decode(status.favicon.split(",", 1)[1])), filename="icon.png"
            )
            if status.favicon
            else None
        )
        embed = discord.Embed(
            title=f"{server.host}:{server.port}",
            description=await self.clear_mcformatting(status.description),
            color=await ctx.embed_color(),
        )
        if icon:
            embed.set_thumbnail(url="attachment://icon.png")
        embed.add_field(name=_("Latency"), value=f"{status.latency} ms")
        embed.add_field(
            name=_("Players"),
            value="{0.players.online}/{0.players.max}\n{1}".format(
                status,
                status.players.sample
                and list(
                    chat.pagify(
                        await self.clear_mcformatting(
                            "\n".join([p.name for p in status.players.sample])
                        ),
                        page_length=1000,
                    )
                )[0]
                or "",
            ),
        )
        embed.add_field(
            name=_("Version"),
            value=_("{}\nProtocol: {}").format(
                status.version.name, status.version.protocol
            ),
        )
        if query:
            embed.add_field(name=_("World"), value=f"{query.map}")
            embed.add_field(
                name=_("Software"),
                value=_("{}\nVersion: {}").format(
                    query.software.brand, query.software.version
                )
                # f"Plugins: {query.software.plugins}"
            )
        await ctx.send(file=icon, embed=embed)

    @minecraft.command()
    @checks.bot_has_permissions(embed_links=True)
    async def status(self, ctx):
        """Get status of minecraft services"""
        try:
            async with self.session.get("https://status.mojang.com/check") as data:
                data = await data.json()
            em = discord.Embed(
                title=_("Status of minecraft services"),
                timestamp=ctx.message.created_at,
                color=await ctx.embed_color(),
            )
            for service in data:
                for entry, status in service.items():
                    em.add_field(name=entry, value=SERVICE_STATUS.get(status, status))
            await ctx.send(embed=em)
        except Exception as e:
            await ctx.send(
                chat.error(
                    _("Unable to check. An error has been occurred: {}").format(
                        chat.inline(str(e))
                    )
                )
            )

    @minecraft.command(aliases=["nicknames", "nickhistory", "names"])
    async def nicks(self, ctx, current_nick: MCPlayer):
        """Check history of player's nicks"""
        uuid = current_nick.uuid
        try:
            async with self.session.get(
                "https://api.mojang.com/user/profiles/{}/names".format(uuid)
            ) as data:
                data_history = await data.json()
            for nick in data_history:
                try:
                    nick["changedToAt"] = datetime.utcfromtimestamp(
                        nick["changedToAt"] / 1000
                    ).strftime(_("%d.%m.%Y %H:%M:%S"))
                except KeyError:
                    nick["changedToAt"] = _("Initial")
            table = tabulate.tabulate(
                data_history,
                headers={
                    "name": _("Nickname"),
                    "changedToAt": _("Changed to at... (UTC)"),
                },
                tablefmt="orgtbl",
            )
            pages = [chat.box(page) for page in list(chat.pagify(table))]
            await menu(ctx, pages, DEFAULT_CONTROLS)
        except Exception as e:
            await ctx.send(
                chat.error(
                    _("Unable to check name history.\nAn error has been occurred: ")
                    + chat.inline(str(e))
                )
            )

    async def clear_mcformatting(self, formatted_str) -> str:
        """Remove Minecraft-formatting"""
        if isinstance(formatted_str, dict):
            clean = ""
            async for text in self.gen_dict_extract("text", formatted_str):
                clean += text
            clean = re.sub(r"\xA7[0-9A-FK-OR]", "", clean, flags=re.IGNORECASE)
        else:
            clean = re.sub(r"\xA7[0-9A-FK-OR]", "", formatted_str, flags=re.IGNORECASE)
        return clean

    async def gen_dict_extract(self, key, var):
        if hasattr(var, "items"):
            for k, v in var.items():
                if k == key:
                    yield v
                if isinstance(v, dict):
                    async for result in self.gen_dict_extract(key, v):
                        yield result
                elif isinstance(v, list):
                    for d in v:
                        async for result in self.gen_dict_extract(key, d):
                            yield result
