import colorsys
import datetime
import random

import aiohttp
import discord
from redbot.core import checks, commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from tabulate import tabulate

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json


T_ = Translator("MoreUtils", __file__)
_ = lambda s: s

DISCORD_STATUS_NAMES = {
    "none": _("OK"),
    "minor": _("Minor problems"),
    "major": _("Major problems"),
    "critical": _("Critical problems"),
}

_ = T_


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
    """Some (maybe) useful utils."""

    __version__ = "2.0.15"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(json_serialize=json.dumps)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def red_delete_data_for_user(self, **kwargs):
        return

    @commands.command(name="thetime")
    async def _thetime(self, ctx):
        """Displays the current time of the server."""
        await ctx.send(datetime.datetime.now().strftime(_("%d.%m.%Y %H:%M:%S %Z")))

    @commands.command(aliases=["HEX", "hex", "colour"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.max_concurrency(1, commands.BucketType.user)
    async def color(self, ctx, *, color: discord.Color):
        """Shows some info about provided color."""
        colorrgb = color.to_rgb()
        colorhsv = colorsys.rgb_to_hsv(colorrgb[0], colorrgb[1], colorrgb[2])
        colorhls = colorsys.rgb_to_hls(colorrgb[0], colorrgb[1], colorrgb[2])
        coloryiq = colorsys.rgb_to_yiq(colorrgb[0], colorrgb[1], colorrgb[2])
        colorcmyk = rgb_to_cmyk(colorrgb[0], colorrgb[1], colorrgb[2])
        colors_text = (
            "HEX: {}\n"
            "RGB: {}\n"
            "CMYK: {}\n"
            "HSV: {}\n"
            "HLS: {}\n"
            "YIQ: {}\n"
            "int: {}".format(
                str(color),
                colorrgb,
                tuple(map(lambda x: isinstance(x, float) and round(x, 2) or x, colorcmyk)),
                tuple(map(lambda x: isinstance(x, float) and round(x, 2) or x, colorhsv)),
                tuple(map(lambda x: isinstance(x, float) and round(x, 2) or x, colorhls)),
                tuple(map(lambda x: isinstance(x, float) and round(x, 2) or x, coloryiq)),
                color.value,
            )
        )
        em = discord.Embed(
            title=str(color),
            description=_("Name: Loading...\n") + colors_text,
            url=f"http://www.color-hex.com/color/{str(color)[1:]}",
            colour=color,
            timestamp=ctx.message.created_at,
        )
        em.set_thumbnail(url=f"https://api.alexflipnote.dev/color/image/{str(color)[1:]}")
        em.set_image(url=f"https://api.alexflipnote.dev/color/image/gradient/{str(color)[1:]}")
        m = await ctx.send(embed=em)
        async with self.session.get(
            f"https://api.alexflipnote.dev/color/{str(color)[1:]}"
        ) as data:
            color_name = (await data.json(loads=json.loads)).get("name", "?")
        em.description = _("Name: {}\n").format(color_name) + colors_text
        await m.edit(embed=em)

    @commands.guild_only()
    @commands.command()
    async def someone(self, ctx, *, text: str = None):
        """Help I've fallen and I need @someone.

        Discord 2018 April Fools."""
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
    @commands.max_concurrency(1, commands.BucketType.user)
    async def discordstatus(self, ctx):
        """Get current discord status from discordstatus.com"""
        async with ctx.typing():
            try:
                async with self.session.get(
                    "https://srhpyqt94yxb.statuspage.io/api/v2/summary.json"
                ) as data:
                    response = await data.json(loads=json.loads)
            except Exception as e:
                await ctx.send(
                    chat.error(
                        _("Unable to get data from https://discordstatus.com: {}").format(e)
                    )
                )
                return
            status = response["status"]
            components = response["components"]
            if await ctx.embed_requested():
                embed = discord.Embed(
                    title=_("Discord Status"),
                    description=_(
                        DISCORD_STATUS_NAMES.get(status["indicator"], status["indicator"])
                    ),
                    timestamp=datetime.datetime.fromisoformat(response["page"]["updated_at"])
                    .astimezone(datetime.timezone.utc)
                    .replace(tzinfo=None),  # make naive
                    color=await ctx.embed_color(),
                    url="https://discordstatus.com",
                )
                for component in components:
                    embed.add_field(
                        name=component["name"],
                        value=component["status"].capitalize().replace("_", " "),
                    )
                await ctx.send(embed=embed)
            else:
                await ctx.send(
                    f"{_(DISCORD_STATUS_NAMES.get(status['indicator'], status['indicator']))}\n"
                    f"{chat.box(tabulate([(c['name'], c['status'].capitalize().replace('_', ' ')) for c in components]))}"
                )
