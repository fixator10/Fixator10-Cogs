from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands
from validators import url

from cogs.utils.chat_formatting import *


class MemeGen:
    """Make memes with bot!"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def __unload(self):
        self.session.close()

    @commands.group(pass_context=True)
    async def meme(self, ctx):
        """Make memes with bot!"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @meme.command()
    async def embed(self, template: str, upper_text: str = "", down_text: str = "", font: str = "impact"):
        """Show meme via embed"""
        link = await self.get_meme(template, upper_text, down_text, font)
        if not link:
            await self.bot.say("This template not found")
            return
        embed = discord.Embed()
        embed.set_image(url=link)
        embed.set_footer(text="https://memegen.link/", icon_url="https://memegen.link/images/favicon-16x16.png")
        await self.bot.say(embed=embed)

    @meme.command()
    async def link(self, template: str, upper_text: str = "", down_text: str = "", font: str = "impact"):
        """Show meme via link"""
        link = await self.get_meme(template, upper_text, down_text, font)
        if not link:
            await self.bot.say("This template not found")
            return
        await self.bot.say(link)

    @meme.command()
    async def fonts(self):
        """Get list of fonts"""
        font_list = await self.get_fonts()
        await self.bot.say(box("\n".join([str(x) for x in font_list])))

    async def get_template(self, template: str):
        if url(template):
            return "custom"
        async with self.session.get("https://memegen.link/api/search/{}".format(template)) as data:
            data = await data.json()
        if data:
            return data[0]["template"]["blank"].replace("https://memegen.link/", "").replace("/_.jpg", "")
        return None

    async def get_meme(self, template: str, upper_text: str, down_text: str, font: str):
        template = template.replace(" ", "-")
        if upper_text == "":
            upper_text = "_"
        if down_text == "":
            down_text = "_"
        upper_text = quote(upper_text.replace("/", "~s"))
        down_text = quote(down_text.replace("/", "~s"))
        if url(template):
            template_url = template
        template = await self.get_template(template)
        if template is None:
            return
        link = "https://memegen.link/{}/{}/{}.jpg?font={}".format(template, upper_text, down_text, font)
        if template == "custom":
            link += "&alt={}".format(template_url)
        return link

    async def get_fonts(self):
        async with self.session.get("https://memegen.link/api/fonts") as data:
            return await data.json()


def setup(bot):
    bot.add_cog(MemeGen(bot))
