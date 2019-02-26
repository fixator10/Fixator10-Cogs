import base64
import io
from datetime import datetime

import aiohttp
import discord
import tabulate
from redbot.core import commands
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from .converters import MCNickname


class MinecraftData(commands.Cog):
    """Minecraft-Related data"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def __unload(self):
        self.session.close()

    @commands.group(name="minecraft", aliases=["mc"])
    async def minecraft(self, ctx):
        """Get Minecraft-Related data"""
        pass

    @minecraft.command()
    async def skin(self, ctx, nickname: MCNickname, helm_layer: bool = True):
        """Get minecraft skin by nickname"""
        uuid = nickname.uuid
        if uuid is None:
            await ctx.send(chat.error("This player not found"))
            return
        em = discord.Embed(timestamp=ctx.message.created_at, color=await ctx.embed_color())
        # em.add_field(name="NameMC profile", value="[{}](https://namemc.com/profile/{})".format(nickname, uuid))
        em.set_author(name=nickname.name,
                      icon_url="https://crafatar.com/renders/head/{}{}".format(uuid, "?overlay" if helm_layer else ""),
                      url="https://crafatar.com/skins/{}".format(uuid))
        em.set_thumbnail(url="https://crafatar.com/skins/{}".format(uuid))
        em.set_image(url="https://crafatar.com/renders/body/{}.png{}".format(uuid, "?overlay" if helm_layer else ""))
        em.set_footer(text="Provided by Crafatar", icon_url="https://crafatar.com/logo.png")
        await ctx.send(embed=em)

    @minecraft.group(invoke_without_command=True)
    async def cape(self, ctx):
        """Get minecraft cape by nickname"""
        await ctx.send_help()

    @cape.command(aliases=["of"])
    async def optifine(self, ctx, nickname: MCNickname):
        """Get optifine cape by nickname"""
        em = discord.Embed(timestamp=ctx.message.created_at, color=await ctx.embed_color())
        em.set_author(name=nickname.name, url="http://s.optifine.net/capes/{}.png".format(nickname.name))
        em.set_image(url="http://s.optifine.net/capes/{}.png".format(nickname.name))
        await ctx.send(embed=em)

    @cape.command()
    async def labymod(self, ctx, nickname: MCNickname):
        """Get LabyMod cape by nickname"""
        uuid = nickname.dashed_uuid
        if uuid is None:
            await ctx.send(chat.error("This player not found"))
            return
        try:
            async with self.session.get('http://capes.labymod.net/capes/' + uuid) as data:
                if data.status == 404:
                    await ctx.send(chat.error("404. Player not found on LabyMod's servers."))
                    return
                cape = await data.read()
        except Exception as e:
            await ctx.send(chat.error("Data is not found. (Or LabyMod capes server is down)\n{}"
                                      .format(chat.inline(str(e)))))
            return
        cape = io.BytesIO(cape)
        file = discord.File(cape, filename="{}.png".format(nickname))
        await ctx.send(file=file)
        cape.close()

    @cape.command(aliases=["minecraftcapes", "couk"])
    async def mccapes(self, ctx, nickname: MCNickname):
        """Get MinecraftCapes.co.uk cape by nickname"""
        uuid = nickname.uuid
        if uuid is None:
            await ctx.send(chat.error("This player not found"))
            return
        em = discord.Embed(timestamp=ctx.message.created_at, color=await ctx.embed_color())
        em.set_author(name=nickname.name, url="https://www.minecraftcapes.co.uk/getCape.php?uuid={}".format(uuid))
        em.set_image(url="https://www.minecraftcapes.co.uk/getCape.php?uuid={}".format(uuid))
        await ctx.send(embed=em)

    @cape.group(name="5zig", aliases=["fivezig"], invoke_without_command=True)
    async def fivezig(self, ctx, nickname: MCNickname):
        """Get 5zig cape by nickname"""
        await ctx.invoke(self._fivezig_cape, nickname=nickname)

    @fivezig.command(name="cape")
    async def _fivezig_cape(self, ctx, nickname: MCNickname):
        """Get 5zig cape by nickname"""
        uuid = nickname.uuid
        if uuid is None:
            await ctx.send(chat.error("This player not found"))
            return
        try:
            async with self.session.get('http://textures.5zig.net/textures/2/' + uuid) as data:
                response_data = await data.json(content_type=None)
            cape = response_data["cape"]
        except Exception as e:
            await ctx.send(chat.error("Data is not found. (Or 5zig texture server is down)\n{}"
                                      .format(chat.inline(str(e)))))
            return
        cape = io.BytesIO(base64.decodebytes(cape.encode()))
        file = discord.File(cape, filename="{}.png".format(nickname))
        await ctx.send(file=file)
        cape.close()

    @fivezig.command(name="animated")
    async def _fivezig_animated(self, ctx, nickname: MCNickname):
        """Get 5zig animated cape by nickname"""
        uuid = nickname.uuid
        if uuid is None:
            await ctx.send(chat.error("This player not found"))
            return
        try:
            async with self.session.get('http://textures.5zig.net/textures/2/' + uuid) as data:
                response_data = await data.json(content_type=None)
            if "animatedCape" not in response_data:
                await ctx.send(chat.error("{} doesn't have animated cape").format(nickname.name))
                return
            cape = response_data["animatedCape"]
        except Exception as e:
            await ctx.send(chat.error("Data is not found. (Or 5zig texture server is down)\n{}"
                                      .format(chat.inline(str(e)))))
            return
        cape = io.BytesIO(base64.decodebytes(cape.encode()))
        file = discord.File(cape, filename="{}.png".format(nickname))
        await ctx.send(file=file)
        cape.close()

    # TODO: find new library/api for that
    # @minecraft.command()
    # async def server(self, ctx, IP_or_domain: str):
    #     """Get info about server"""

    @minecraft.command()
    async def status(self, ctx):
        """Get status of minecraft services"""
        try:
            async with self.session.get('https://status.mojang.com/check') as data:
                data = await data.json()
            em = discord.Embed(title="Status of minecraft services", timestamp=ctx.message.created_at,
                               color=await ctx.embed_color())
            for service in data:
                for entry, status in service.items():
                    em.add_field(name=entry, value=status.replace("red", "💔 **UNAVAILABLE**") \
                                 .replace("yellow", "💛 **SOME ISSUES**") \
                                 .replace("green", "💚 **OK**"))
            await ctx.send(embed=em)
        except Exception as e:
            await ctx.send(chat.error("Unable to check. An error has been occurred: {}".format(chat.inline(str(e)))))

    @minecraft.command(aliases=["nicknames", "nickhistory"])
    async def nicks(self, ctx, current_nick: MCNickname):
        """Check history of user's nicks"""
        uuid = current_nick.uuid
        if uuid is None:
            await ctx.send(chat.error("This player not found"))
            return
        try:
            async with self.session.get('https://api.mojang.com/user/'
                                        'profiles/{}/names'.format(uuid)) as data:
                data_history = await data.json()
            for nick in data_history:
                try:
                    nick["changedToAt"] = \
                        datetime.utcfromtimestamp(nick["changedToAt"] / 1000).strftime('%d.%m.%Y %H:%M:%S')
                except KeyError:
                    nick["changedToAt"] = "Initial"
            table = tabulate.tabulate(data_history, headers={"name": "Nickname",
                                                             "changedToAt": "Changed to at... (UTC)"},
                                      tablefmt="orgtbl")
            pages = [chat.box(page) for page in list(chat.pagify(table))]
            await menu(ctx, pages, DEFAULT_CONTROLS)
        except Exception as e:
            await ctx.send(chat.error("Unable to check name history.\nAn error has been occurred: " +
                                      chat.inline(str(e))))
