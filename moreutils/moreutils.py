import colorsys
import datetime
import random

import aiohttp
import discord
from dateutil.parser import parse
from redbot.core import checks
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat

_ = Translator("MoreUtils", __file__)


def rgb_to_cmyk(r, g, b):
    rgb_scale = 255
    cmyk_scale = 100
    if (r == 0) and (g == 0) and (b == 0):
        # black
        return 0, 0, 0, cmyk_scale

    # rgb [0,255] -> cmy [0,1]
    c = 1 - r / float(rgb_scale)
    m = 1 - g / float(rgb_scale)
    y = 1 - b / float(rgb_scale)

    # extract out k [0,1]
    min_cmy = min(c, m, y)
    c = c - min_cmy
    m = m - min_cmy
    y = y - min_cmy
    k = min_cmy

    # rescale to the range [0,cmyk_scale]
    return c * cmyk_scale, m * cmyk_scale, y * cmyk_scale, k * cmyk_scale


def bool_emojify(bool_var: bool) -> str:
    return "✅" if bool_var else "❌"


@cog_i18n(_)
class MoreUtils(commands.Cog):
    # noinspection PyMissingConstructor
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.command(name="thetime")
    async def _thetime(self, ctx):
        """Send bot's current time"""
        await ctx.send(datetime.datetime.now().strftime(_("%d.%m.%Y %H:%M:%S %Z")))

    @commands.command(aliases=["HEX", "hex"])
    @checks.bot_has_permissions(embed_links=True)
    async def color(self, ctx, color: discord.Color):
        """Shows some info about provided color"""
        colorrgb = color.to_rgb()
        colorhsv = colorsys.rgb_to_hsv(colorrgb[0], colorrgb[1], colorrgb[2])
        colorhls = colorsys.rgb_to_hls(colorrgb[0], colorrgb[1], colorrgb[2])
        coloryiq = colorsys.rgb_to_yiq(colorrgb[0], colorrgb[1], colorrgb[2])
        colorcmyk = rgb_to_cmyk(colorrgb[0], colorrgb[1], colorrgb[2])
        em = discord.Embed(
            title=str(color),
            description="HEX: {}\n"
            "RGB: {}\n"
            "CMYK: {}\n"
            "HSV: {}\n"
            "HLS: {}\n"
            "YIQ: {}\n"
            "int: {}".format(
                hex(color.value).replace("0x", "#"),
                colorrgb,
                colorcmyk,
                colorhsv,
                colorhls,
                coloryiq,
                color.value,
            ),
            url=f"http://www.color-hex.com/color/{hex(color.value).lstrip('0x')}",
            colour=color,
            timestamp=ctx.message.created_at,
        )
        em.set_thumbnail(
            url="https://xenforo.com/rgba.php?r={}&g={}&b={}&a=255".format(
                colorrgb[0], colorrgb[1], colorrgb[2]
            )
        )
        await ctx.send(embed=em)

    @commands.command(pass_context=True, no_pm=True)
    async def someone(self, ctx, *, text: str = None):
        """Help I've fallen and I need @someone.

        Discord 2018 April Fools"""
        smilies = [
            "¯\\_(ツ)_/¯",
            "(∩ ͡° ͜ʖ ͡°)⊃━☆ﾟ. o ･ ｡ﾟ",
            "(∩ ͡° ͜ʖ ͡°)⊃━✿✿✿✿✿✿",
            "༼ つ ◕_◕ ༽つ",
            "(◕‿◕✿)",
            "(⁄ ⁄•⁄ω⁄•⁄ ⁄)",
            "(╯°□°）╯︵ ┻━┻",
            "ಠ_ಠ",
            "¯\\(°_o)/¯",
            "（✿ ͡◕ ᴗ◕)つ━━✫・o。",
            "ヽ༼ ಠ益ಠ ༽ﾉ",
        ]
        smile = random.choice(smilies)
        member = random.choice(ctx.channel.members)
        await ctx.send(
            "**@someone** {} ***{}*** {}".format(
                smile,
                chat.escape(member.display_name, mass_mentions=True),
                chat.escape(text, mass_mentions=True) if text else "",
            )
        )

    @commands.command(pass_context=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def discordstatus(self, ctx):
        """Get current discord status from status.discordapp.com"""
        try:
            async with self.session.get(
                "https://srhpyqt94yxb.statuspage.io/api/v2/summary.json"
            ) as data:
                response = await data.json()
        except Exception as e:
            await ctx.send(
                chat.error(
                    _(
                        "Unable to get data from https://status.discordapp.com: {}"
                    ).format(e)
                )
            )
            return
        status = response["status"]
        status_indicators = {
            "none": _("OK"),
            "minor": _("Minor problems"),
            "major": _("Major problems"),
            "critical": _("Critical problems"),
        }
        components = response["components"]
        embed = discord.Embed(
            title=_("Discord Status"),
            timestamp=parse(response["page"]["updated_at"]),
            color=await ctx.embed_color(),
            url="https://status.discordapp.com",
        )
        embed.description = status_indicators.get(
            status["indicator"], status["indicator"]
        )
        for component in components:
            embed.add_field(
                name=component["name"],
                value=component["status"].capitalize().replace("_", " "),
            )
        await ctx.send(embed=embed)
