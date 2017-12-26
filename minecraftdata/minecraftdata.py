import discord
from discord.ext import commands
import aiohttp
from datetime import datetime
from cogs.utils import chat_formatting as chat
import tabulate
from random import choice


class MinecraftData:
    """Minecraft-Related data"""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    @commands.group(name="minecraft", aliases=["mc"], pass_context=True)
    async def minecraft(self, ctx):
        """Get Minecraft-Related data"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @minecraft.command(pass_context=True)
    async def skin(self, ctx, nickname: str, helm_layer: bool = True):
        """Get minecraft skin by nickname"""
        helm_layer = str(helm_layer).lower()
        em = discord.Embed(timestamp=ctx.message.timestamp,
                           url="https://use.gameapis.net/mc/images/rawskin/{}".format(nickname))
        em.set_footer(text="Provided by GameAPIs.net")
        em.set_author(name=nickname,
                      icon_url="https://use.gameapis.net/mc/images/avatar/{}/{}".format(nickname, helm_layer))
        em.set_thumbnail(url="https://use.gameapis.net/mc/images/rawskin/{}".format(nickname))
        em.set_image(url="https://use.gameapis.net/mc/images/skin/{}/{}".format(nickname, helm_layer))
        await self.bot.say(embed=em)

    # @minecraft.command(pass_context=True)
    # async def isup(self, ctx, IP_or_domain: str):
    #     """Is minecraft server up or down?"""
    #     try:
    #         async with self.session.get('https://use.gameapis.net/mc/isup/' + IP_or_domain) as data:
    #             data = await data.json()
    #         await self.bot.say(data["message"])
    #     except Exception as e:
    #         await self.bot.say(chat.error("Unable to check. An error has been occurred: " + chat.inline(e)))

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
        """Check history of user's nicks history"""
        userid = await self.getuserid(current_nick)
        if userid is None:
            await self.bot.say(chat.error("This user not found"))
            return
        try:
            async with self.session.get('https://api.mojang.com/user/'
                                        'profiles/{}/names'.format(userid)) as data:
                data_history = await data.json()
            for nick in data_history:
                try:
                    nick["changedToAt"] = \
                        datetime.utcfromtimestamp(nick["changedToAt"] / 1000).strftime('%d.%m.%Y %H:%M:%S')
                except:
                    nick["changedToAt"] = "Initial"
            await self.bot.say(chat.box(tabulate.tabulate(data_history,
                                                          headers={"name": "Nickname",
                                                                   "changedToAt": "Changed to at..."},
                                                          tablefmt="fancy_grid")))
        except Exception as e:
            await self.bot.say(chat.error("Unable to check name history.\nAn error has been occurred: " +
                                          chat.inline(e)))

    async def getuserid(self, nickname: str):
        try:
            async with self.session.get('https://api.mojang.com/users/profiles/minecraft/' + nickname) as data:
                response_data = await data.json()
        except:
            return None
        if response_data is None:
            return None
        else:
            userid = str(response_data["id"])
            return userid


def setup(bot):
    bot.add_cog(MinecraftData(bot))
