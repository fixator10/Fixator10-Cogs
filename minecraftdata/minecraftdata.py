import base64
import io
from datetime import datetime
from random import choice
from uuid import UUID

import aiohttp
import discord
import tabulate
from discord.ext import commands

from cogs.utils import chat_formatting as chat


class MinecraftData:
    """Minecraft-Related data"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def __unload(self):
        self.session.close()

    @commands.group(name="minecraft", aliases=["mc"], pass_context=True)
    async def minecraft(self, ctx):
        """Get Minecraft-Related data"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @minecraft.command(pass_context=True)
    async def skin(self, ctx, nickname: str, helm_layer: bool = True):
        """Get minecraft skin by nickname"""
        uuid = await self.getuuid(nickname)
        if uuid is None:
            await self.bot.say(chat.error("This player not found"))
            return
        em = discord.Embed(timestamp=ctx.message.timestamp)
        em.set_footer(text="Provided by Crafatar")
        em.set_author(name=nickname,
                      icon_url="https://crafatar.com/renders/head/{}{}".format(uuid, "?overlay" if helm_layer else ""),
                      url="https://crafatar.com/skins/{}".format(uuid))
        em.set_thumbnail(url="https://crafatar.com/skins/{}".format(uuid))
        em.set_image(url="https://crafatar.com/renders/body/{}{}".format(uuid, "?overlay" if helm_layer else ""))
        await self.bot.say(embed=em)

    @minecraft.group(pass_context=True, invoke_without_command=True)
    async def cape(self, ctx):
        """Get minecraft cape by nickname"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @cape.command(pass_context=True, aliases=["of"])
    async def optifine(self, ctx, nickname: str):
        """Get optifine cape by nickname"""
        em = discord.Embed(timestamp=ctx.message.timestamp)
        em.set_author(name=nickname, url="http://s.optifine.net/capes/{}.png".format(nickname))
        em.set_image(url="http://s.optifine.net/capes/{}.png".format(nickname))
        await self.bot.say(embed=em)

    # TODO: Rework images loading [?]
    # @cape.command(pass_context=True)
    # async def labymod(self, ctx, nickname: str):
    #     """Get LabyMod cape by nickname"""
    #     uuid = await self.getuuid(nickname, dashed=True)
    #     if uuid is None:
    #         await self.bot.say(chat.error("This player not found"))
    #         return
    #     em = discord.Embed(timestamp=ctx.message.timestamp)
    #     em.set_author(name=nickname, url="http://capes.labymod.net/capes/{}".format(uuid))
    #     em.set_image(url="http://capes.labymod.net/capes/{}".format(uuid))
    #     await self.bot.say(embed=em)

    @cape.command(pass_context=True, aliases=["minecraftcapes", "couk"])
    async def mccapes(self, ctx, nickname: str):
        """Get MinecraftCapes.co.uk cape by nickname"""
        uuid = await self.getuuid(nickname)
        if uuid is None:
            await self.bot.say(chat.error("This player not found"))
            return
        em = discord.Embed(timestamp=ctx.message.timestamp)
        em.set_author(name=nickname, url="https://www.minecraftcapes.co.uk/getCape.php?uuid={}".format(uuid))
        em.set_image(url="https://www.minecraftcapes.co.uk/getCape.php?uuid={}".format(uuid))
        await self.bot.say(embed=em)

    # TODO: BASE64 PNG decryption
    @cape.command(name="5zig", pass_context=True, aliases=["fivezig"])
    async def _5zig(self, ctx, nickname: str):
        """Get 5zig cape by nickname"""
        uuid = await self.getuuid(nickname)
        if uuid is None:
            await self.bot.say(chat.error("This player not found"))
            return
        # em = discord.Embed(timestamp=ctx.message.timestamp)
        # em.set_author(name=nickname, url="http://textures.5zig.net/textures/2/{}".format(uuid))
        # em.set_image(url="http://textures.5zig.net/textures/2/{}".format(uuid))
        # await self.bot.say(embed=em)
        try:
            async with self.session.get('http://textures.5zig.net/textures/2/' + uuid) as data:
                response_data = await data.json(content_type='text/plain')
            cape = response_data["cape"]
        except:
            await self.bot.say(chat.error("Player is not found. (Or 5zig texture server is down)"))
            return
        file = io.BytesIO(base64.decodebytes(cape.encode()))
        await self.bot.send_file(ctx.message.channel, file, filename="{}.png".format(nickname))

    @minecraft.command(pass_context=True)
    async def server(self, ctx, IP_or_domain: str):
        """Get info about server"""
        banner_style = choice(["", "sunset", "night", "nether"])
        try:
            async with self.session.get('https://use.gameapis.net/mc/query/info/{}'.format(IP_or_domain)) as data:
                data = await data.json()
            em = discord.Embed(title="Server data: " + IP_or_domain, timestamp=ctx.message.timestamp)
            em.set_footer(text="Provided by GameAPIs.net")
            em.add_field(name="Status", value=str(data["status"]).replace("True", "OK").replace("False", "Not OK"))
            em.set_thumbnail(url="https://use.gameapis.net/mc/query/icon/{}".format(IP_or_domain))
            em.set_image(url="https://use.gameapis.net/mc/query/banner/{}/{}".format(IP_or_domain, banner_style))
            if data["status"]:
                em.description = "**MOTD:**{}".format(chat.box(data["motds"]["clean"]))
                em.add_field(name="Ping", value=data["ping"] or chat.inline("N/A"))
                em.add_field(name="Version", value="{} (Protocol: {})".format(data["version"], data["protocol"]))
                em.add_field(name="Players", value="{}/{}".format(data["players"]["online"], data["players"]["max"]))
            else:
                em.add_field(name="Error", value="Unable to fetch server: {}".format(chat.inline(data["error"])))
            await self.bot.say(embed=em)
        except Exception as e:
            await self.bot.say(chat.error("Unable to check. An error has been occurred: " + chat.inline(e)))

    @minecraft.command(pass_context=True)
    async def status(self, ctx):
        """Get status of minecraft services"""
        try:
            async with self.session.get('https://status.mojang.com/check') as data:
                data = await data.json()
            em = discord.Embed(title="Status of minecraft services", timestamp=ctx.message.timestamp)
            for service in data:
                for entry, status in service.items():
                    em.add_field(name=entry, value=status.replace("red", "💔 **UNAVAILABLE**") \
                                 .replace("yellow", "💛 **SOME ISSUES**") \
                                 .replace("green", "💚 **OK**"))
            await self.bot.say(embed=em)
        except Exception as e:
            await self.bot.say(chat.error("Unable to check. An error has been occurred: {}".format(chat.inline(e))))

    @minecraft.command(pass_context=True, aliases=["nicknames", "nickhistory"])
    async def nicks(self, ctx, current_nick: str):
        """Check history of user's nicks"""
        uuid = await self.getuuid(current_nick)
        if uuid is None:
            await self.bot.say(chat.error("This player not found"))
            return
        try:
            async with self.session.get('https://api.mojang.com/user/'
                                        'profiles/{}/names'.format(uuid)) as data:
                data_history = await data.json()
            async with self.session.get('https://api.mojang.com/users/profiles/minecraft/' + current_nick) as data:
                response = await data.json()
                createdAt = response["createdAt"]
            for nick in data_history:
                try:
                    nick["changedToAt"] = \
                        datetime.utcfromtimestamp(nick["changedToAt"] / 1000).strftime('%d.%m.%Y %H:%M:%S')
                except:
                    nick["changedToAt"] = datetime.utcfromtimestamp(createdAt / 1000).strftime('%d.%m.%Y %H:%M:%S')
            table = tabulate.tabulate(data_history, headers={"name": "Nickname",
                                                             "changedToAt": "Changed to at... (UTC)"},
                                      tablefmt="fancy_grid")
            for page in chat.pagify(table):
                await self.bot.say(chat.box(page))
        except Exception as e:
            await self.bot.say(chat.error("Unable to check name history.\nAn error has been occurred: " +
                                          chat.inline(e)))

    async def getuuid(self, nickname: str, *, dashed: bool = False):
        """Get UUID by player's nickname

        Return None if player not found"""
        try:
            async with self.session.get('https://api.mojang.com/users/profiles/minecraft/' + nickname) as data:
                response_data = await data.json()
        except:
            return None
        if response_data is None or "id" not in response_data:
            return None
        else:
            uuid = str(response_data["id"])
            if dashed:
                uuid = str(UUID(hex=uuid))
            return uuid


def setup(bot):
    bot.add_cog(MinecraftData(bot))
