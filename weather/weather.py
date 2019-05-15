import datetime
from functools import partial

import discord
import forecastio
import geocoder
from redbot.core import checks
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from requests.exceptions import (
    HTTPError,
    ConnectionError as RequestsConnectionError,
    Timeout,
)

_ = Translator("MinecraftData", __file__)

WEATHER_STATES = {
    "clear-day": "\N{Black Sun with Rays}",
    "clear-night": "\N{Night with Stars}",
    "rain": "\N{Cloud with Rain}",
    "snow": "\N{Cloud with Snow}",
    "sleet": "\N{Snowflake}",
    "wind": "\N{Wind Blowing Face}",
    "fog": "\N{Foggy}",
    "cloudy": "\N{White Sun Behind Cloud}",
    "partly-cloudy-day": "\N{White Sun with Small Cloud}",
    "partly-cloudy-night": "\N{Night with Stars}",
}


@cog_i18n(_)
class Weather(commands.Cog):
    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @checks.is_owner()
    async def forecastapi(self, ctx):
        """Set API key for forecast.io"""
        message = _(
            "To get forecast.io API key:\n"
            "1. Register/login at [DarkSky](https://darksky.net/dev/register)\n"
            '2. Copy ["Your Secret Key"](https://darksky.net/dev/account)\n'
            "3. Use `{}set api forecastio secret,<your_apikey>`"
        ).format(ctx.prefix)
        await ctx.maybe_send_embed(message)

    @commands.command()
    @commands.guild_only()
    async def weather(self, ctx, *, place: str):
        """Shows weather in provided place"""
        apikeys = await self.bot.db.api_tokens.get_raw(
            "forecastio", default={"secret": None}
        )
        g = await self.bot.loop.run_in_executor(None, geocoder.komoot, place)
        if not g.latlng:
            await ctx.send(
                chat.error(_("Cannot find a place {}").format(chat.inline(place)))
            )
            return
        try:
            forecast = await self.bot.loop.run_in_executor(
                None,
                partial(
                    forecastio.load_forecast,
                    apikeys["secret"],
                    g.latlng[0],
                    g.latlng[1],
                    units="si",
                ),
            )
        except HTTPError:
            await ctx.send(
                chat.error(
                    _(
                        "This command requires API key. "
                        "Use {}forecastapi to get more information"
                    ).format(ctx.prefix)
                )
            )
            return
        except (RequestsConnectionError, Timeout):
            await ctx.send(chat.error(_("Unable to get data from forecast.io")))
            return
        by_hour = forecast.currently()
        place = [place for place in [g.city, g.state, g.country] if place]
        place = ", ".join(place)

        content = _("Weather in {}:\n" "{}\n" "{}˚C\n" "{}\n").format(
            place,
            by_hour.summary,
            by_hour.temperature,
            WEATHER_STATES.get(by_hour.icon, "\N{Black Sun with Rays}"),
        )
        em = discord.Embed(
            description=content, color=await ctx.embed_color(), timestamp=by_hour.time
        )
        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            await ctx.send(embed=em)
        else:
            await ctx.send(content)

    @commands.command()
    @commands.guild_only()
    async def forecast(self, ctx, *, place: str):
        """Shows 7 days forecast for provided place"""
        apikeys = await self.bot.db.api_tokens.get_raw(
            "forecastio", default={"secret": None}
        )
        g = await self.bot.loop.run_in_executor(None, geocoder.komoot, place)
        if not g.latlng:
            await ctx.send(_("Cannot find a place {}").format(chat.inline(place)))
            return
        try:
            forecast = await self.bot.loop.run_in_executor(
                None,
                partial(
                    forecastio.load_forecast,
                    apikeys["secret"],
                    g.latlng[0],
                    g.latlng[1],
                    units="si",
                ),
            )
        except HTTPError:
            await ctx.send(
                chat.error(
                    _(
                        "This command requires API key. "
                        "Use {}forecastapi to get more information"
                    ).format(ctx.prefix)
                )
            )
            return
        except (RequestsConnectionError, Timeout):
            await ctx.send(chat.error(_("Unable to get data from forecast.io")))
            return
        by_hour = forecast.daily()
        place = [place for place in [g.city, g.state, g.country] if place]
        place = ", ".join(place)

        content = _("Weather in {}:\n").format(place)
        for i in range(0, 7):
            content = content + "__**{}**__:       {} - {}˚C       {}\n".format(
                by_hour.data[i].time.strftime("%d.%m"),
                by_hour.data[i].temperatureMin or "\N{White Question Mark Ornament}",
                by_hour.data[i].temperatureMax or "\N{White Question Mark Ornament}",
                WEATHER_STATES.get(by_hour.data[i].icon) or "\N{Black Sun with Rays}",
            )
        em = discord.Embed(
            description=content,
            color=await ctx.embed_color(),
            timestamp=datetime.datetime.now(),
        )
        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            await ctx.send(embed=em)
        else:
            await ctx.send(content)
