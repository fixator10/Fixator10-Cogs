from functools import partial
from textwrap import shorten

import aiohttp
import discord
import forecastio
from forecastio.utils import PropertyUnavailable
from redbot.core import __version__ as redbot_ver
from redbot.core import checks, commands
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n, get_locale
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json

FORECASTIO_SUPPORTED_LANGS = [
    "ar",
    "az",
    "be",
    "bg",
    "bn",
    "bs",
    "ca",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "eo",
    "es",
    "et",
    "fi",
    "fr",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "is",
    "it",
    "ja",
    "ka",
    "kn",
    "ko",
    "kw",
    "lv",
    "ml",
    "mr",
    "nb",
    "nl",
    "no",
    "pa",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "sr",
    "sv",
    "ta",
    "te",
    "tr",
    "uk",
    "ur",
    "x-pig-latin",
    "zh",
    "zh-tw",
]

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

# Emoji that will be used for "unknown" strings
UNKNOWN_EMOJI = "\N{White Question Mark Ornament}"

T_ = Translator("Weather", __file__)
_ = lambda s: s

UNITS = {
    "si": {
        "distance": _("km"),
        "intensity": _("mm/h"),
        "accumulation": _("cm"),
        "temp": _("℃"),
        "speed": _("m/s"),
        "pressure": _("hPa"),
    },
    "ca": {
        "distance": _("km"),
        "intensity": _("mm/h"),
        "accumulation": _("cm"),
        "temp": _("℃"),
        "speed": _("km/h"),
        "pressure": _("hPa"),
    },
    "uk2": {
        "distance": _("mi"),
        "intensity": _("mm/h"),
        "accumulation": _("cm"),
        "temp": _("℃"),
        "speed": _("mph"),
        "pressure": _("hPa"),
    },
    "us": {
        "distance": _("mi"),
        "intensity": _("″"),
        "accumulation": _("″"),
        "temp": _("℉"),
        "speed": _("mph"),
        "pressure": _("mbar"),
    },
}

PRECIP_TYPE_I18N = {"rain": _("Rain"), "snow": _("Snow"), "sleet": _("Sleet")}

_ = T_


@cog_i18n(_)
class Weather(commands.Cog):
    """Weather forecast"""

    __version__ = "2.0.5"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xDC5A74E677F24720AA82AD1C237721E7)
        default_guild = {"units": "si"}
        self.config.register_guild(**default_guild)
        self.session = aiohttp.ClientSession(
            json_serialize=json.dumps,
            raise_for_status=True,
        )

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        await self.config.user_from_id(user_id).clear()

    @commands.command()
    @checks.is_owner()
    async def forecastapi(self, ctx):
        """Set API key for forecast.io"""
        message = _(
            "To get forecast.io API key:\n"
            '1. Find your ["Your Secret Key"](https://darksky.net/dev/account)\n'
            "2. Use `{}set api forecastio secret <your_apikey>`\n"
            "Note: DarkSky API is going to close at end of 2021. "
            "Im already aware of this issue and will change API later. "
            "For now you can use cog with already existing API keys."
        ).format(ctx.clean_prefix)
        await ctx.maybe_send_embed(message)

    @commands.group(invoke_without_command=True)
    async def forecastunits(self, ctx, units: str = None):
        """Set forecast units for yourself

        Applicable units:
        si - SI units (default)
        us - Imperial units
        uk2 - Same as si, but distance in miles and speed in mph
        ca - Same as si, but speed in km/h
        reset - reset your unit preference"""
        if not units:
            if ctx.guild:
                await ctx.send(
                    chat.info(
                        _("Your current units are: {}").format(
                            await self.config.user(ctx.author).units()
                            or _("Not set, using server's default {}").format(
                                await self.config.guild(ctx.guild).units()
                            )
                        )
                    )
                )
            else:
                await ctx.send(
                    chat.info(
                        _("Your current units are: {}").format(
                            await self.config.user(ctx.author).units() or "si"
                        )
                    )
                )
            return
        units = units.casefold()
        if units == "reset":
            await self.config.user(ctx.author).units.clear()
            await ctx.tick()
            return
        if units not in UNITS.keys():
            await ctx.send(
                chat.error(
                    _('Units "{}" are not supported, check {}help forecastunits').format(
                        units, ctx.clean_prefix
                    )
                )
            )
            return
        await self.config.user(ctx.author).units.set(units)
        await ctx.tick()

    @forecastunits.command(name="guild")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def set_guild_units(self, ctx, units: str = None):
        """Set forecast units for this guild

        Applicable units:
        si - SI units (default)
        us - Imperial units
        uk2 - Same as si, but distance in miles and speed in mph
        ca - Same as si, but speed in km/h"""
        if not units:
            await ctx.send(
                chat.info(
                    _("Current units are: {}").format(await self.config.guild(ctx.guild).units())
                )
            )
            return
        units = units.casefold()
        if units not in UNITS.keys():
            await ctx.send(
                chat.error(
                    _('Units "{}" are not supported, check {}help forecastunits guild').format(
                        units, ctx.clean_prefix
                    )
                )
            )
            return
        await self.config.guild(ctx.guild).units.set(units)
        await ctx.tick()

    @commands.command()
    @commands.cooldown(1, 1, commands.BucketType.default)
    @commands.bot_has_permissions(embed_links=True)
    async def weather(self, ctx, *, place: str):
        """Shows weather in provided place"""
        apikeys = await self.bot.get_shared_api_tokens("forecastio")
        async with ctx.typing():
            try:
                async with self.session.get(
                    f"https://nominatim.openstreetmap.org/search?q={place}&format=jsonv2&addressdetails=1&limit=1",
                    headers={
                        "Accept-Language": get_locale(),
                        "User-Agent": f"Red-DiscordBot/{redbot_ver} Fixator10-Cogs/Weather/{self.__version__}",
                    },
                ) as r:
                    location = await r.json(loads=json.loads)
            except aiohttp.ClientResponseError as e:
                await ctx.send(
                    chat.error(
                        _("Cannot find a place {}. OSM returned {}").format(
                            chat.inline(place), e.status
                        )
                    )
                )
                return
            if not location:
                await ctx.send(chat.error(_("Cannot find a place {}").format(chat.inline(place))))
                return
            location = location[0]
            try:
                forecast = await self.bot.loop.run_in_executor(
                    None,
                    partial(
                        forecastio.load_forecast,
                        apikeys.get("secret"),
                        location.get("lat", 0),
                        location.get("lon", 0),
                        units=await self.get_units(ctx),
                        lang=await self.get_lang(),
                    ),
                )
            except HTTPError:
                await ctx.send(
                    chat.error(
                        _(
                            "This command requires API key. "
                            "Use {}forecastapi to get more information"
                        ).format(ctx.clean_prefix)
                    )
                )
                return
            except (RequestsConnectionError, Timeout):
                await ctx.send(chat.error(_("Unable to get data from forecast.io")))
                return
        by_hour = forecast.currently()

        em = discord.Embed(
            title=_("Weather in {}").format(
                shorten(location.get("display_name", UNKNOWN_EMOJI), 244, placeholder="…")
            ),
            description=_("[View on Google Maps](https://www.google.com/maps/place/{},{})").format(
                location.get("lat", 0), location.get("lon", 0)
            ),
            color=await ctx.embed_color(),
            timestamp=by_hour.time,
        )
        em.set_author(name=_("Powered by Dark Sky"), url="https://darksky.net/poweredby/")
        em.add_field(
            name=_("Summary"),
            value="{} {}".format(
                WEATHER_STATES.get(by_hour.icon, UNKNOWN_EMOJI),
                by_hour.summary,
            ),
        )
        em.add_field(
            name=_("Temperature"),
            value=f"{by_hour.temperature} {await self.get_localized_units(ctx, 'temp')} "
            f"({by_hour.apparentTemperature} {await self.get_localized_units(ctx, 'temp')})",
        )
        em.add_field(
            name=_("Air pressure"),
            value="{} {}".format(
                by_hour.pressure, await self.get_localized_units(ctx, "pressure")
            ),
        )
        em.add_field(name=_("Humidity"), value=f"{int(by_hour.humidity * 100)}%")
        em.add_field(
            name=_("Visibility"),
            value="{} {}".format(
                by_hour.visibility, await self.get_localized_units(ctx, "distance")
            ),
        )
        em.add_field(
            name=_("Wind speed"),
            value="{} {} {}".format(
                await self.wind_bearing_direction(by_hour.windBearing),
                by_hour.windSpeed,
                await self.get_localized_units(ctx, "speed"),
            ),
        )
        em.add_field(name=_("Cloud cover"), value=f"{int(by_hour.cloudCover * 100)}%")
        em.add_field(
            name=_("Ozone density"),
            value="{} [DU](https://en.wikipedia.org/wiki/Dobson_unit)".format(by_hour.ozone),
        )
        em.add_field(name=_("UV index"), value=by_hour.uvIndex)
        try:
            preciptype = by_hour.precipType
        except PropertyUnavailable:
            preciptype = None
        em.add_field(
            name=_("Precipitation"),
            value=_("Probability: {}%\n").format(int(by_hour.precipProbability * 100))
            + _("Intensity: {} {}").format(
                int(by_hour.precipIntensity * 100),
                await self.get_localized_units(ctx, "intensity"),
            )
            + (
                preciptype
                and _("\nType: {}").format(_(PRECIP_TYPE_I18N.get(preciptype, preciptype)))
                or ""
            ),
        )
        await ctx.send(embed=em)

    @commands.command()
    @commands.cooldown(1, 1, commands.BucketType.default)
    @commands.bot_has_permissions(embed_links=True)
    async def forecast(self, ctx, *, place: str):
        """Shows 7 days forecast for provided place"""
        apikeys = await self.bot.get_shared_api_tokens("forecastio")
        async with ctx.typing():
            try:
                async with self.session.get(
                    f"https://nominatim.openstreetmap.org/search?q={place}&format=jsonv2&addressdetails=1&limit=1",
                    headers={
                        "Accept-Language": get_locale(),
                        "User-Agent": f"Red-DiscordBot/{redbot_ver} Fixator10-Cogs/Weather/{self.__version__}",
                    },
                ) as r:
                    location = await r.json(loads=json.loads)
            except aiohttp.ClientResponseError as e:
                await ctx.send(
                    chat.error(
                        _("Cannot find a place {}. OSM returned {}").format(
                            chat.inline(place), e.status
                        )
                    )
                )
                return
            if not location:
                await ctx.send(chat.error(_("Cannot find a place {}").format(chat.inline(place))))
                return
            location = location[0]
            try:
                forecast = await self.bot.loop.run_in_executor(
                    None,
                    partial(
                        forecastio.load_forecast,
                        apikeys.get("secret"),
                        location.get("lat", 0),
                        location.get("lon", 0),
                        units=await self.get_units(ctx),
                        lang=await self.get_lang(),
                    ),
                )
            except HTTPError:
                await ctx.send(
                    chat.error(
                        _(
                            "This command requires API key. "
                            "Use {}forecastapi to get more information"
                        ).format(ctx.clean_prefix)
                    )
                )
                return
            except (RequestsConnectionError, Timeout):
                await ctx.send(chat.error(_("Unable to get data from forecast.io")))
                return
        by_day = forecast.daily()
        pages = []
        for i in range(0, 8):
            data = by_day.data[i]
            em = discord.Embed(
                title=_("Weather in {}").format(
                    shorten(
                        location.get("display_name", UNKNOWN_EMOJI),
                        244,
                        placeholder="…",
                    )
                ),
                description=f"{by_day.summary}\n"
                + _("[View on Google Maps](https://www.google.com/maps/place/{},{})").format(
                    location.get("lat", 0),
                    location.get("lon", 0),
                ),
                color=await ctx.embed_color(),
                timestamp=data.time,
            )
            em.set_author(name=_("Powered by Dark Sky"), url="https://darksky.net/poweredby/")
            em.set_footer(text=_("Page {}/8").format(i + 1))
            try:
                # FIXME: find a better way to do that
                summary = data.summary
            except PropertyUnavailable:
                summary = _("No summary for this day")
            em.add_field(
                name=_("Summary"),
                value="{} {}".format(
                    WEATHER_STATES.get(data.icon, UNKNOWN_EMOJI),
                    summary,
                ),
            )
            em.add_field(
                name=_("Temperature"),
                value=f"{data.temperatureMin} — {data.temperatureMax} {await self.get_localized_units(ctx, 'temp')}\n"
                f"({data.apparentTemperatureMin} — {data.apparentTemperatureMax}{await self.get_localized_units(ctx, 'temp')})",
            )
            em.add_field(
                name=_("Air pressure"),
                value="{} {}".format(
                    data.pressure, await self.get_localized_units(ctx, "pressure")
                ),
            )
            em.add_field(name=_("Humidity"), value=f"{int(data.humidity * 100)}%")
            em.add_field(
                name=_("Visibility"),
                value="{} {}".format(
                    data.visibility, await self.get_localized_units(ctx, "distance")
                ),
            )
            em.add_field(
                name=_("Wind speed"),
                value="{} {} {}".format(
                    await self.wind_bearing_direction(data.windBearing),
                    data.windSpeed,
                    await self.get_localized_units(ctx, "speed"),
                ),
            )
            em.add_field(name=_("Cloud cover"), value=f"{int(data.cloudCover * 100)}%")
            em.add_field(
                name=_("Ozone density"),
                value="{} [DU](https://en.wikipedia.org/wiki/Dobson_unit)".format(data.ozone),
            )
            em.add_field(name=_("UV index"), value=data.uvIndex)
            try:
                preciptype = data.precipType
            except PropertyUnavailable:
                preciptype = None
            try:
                precipaccumulation = data.precipAccumulation
            except PropertyUnavailable:
                precipaccumulation = None
            em.add_field(
                name=_("Precipitation"),
                value=_("Probability: {}%\n").format(int(data.precipProbability * 100))
                + _("Intensity: {} {}").format(
                    int(data.precipIntensity * 100),
                    await self.get_localized_units(ctx, "intensity"),
                )
                + (
                    preciptype
                    and _("\nType: {}").format(_(PRECIP_TYPE_I18N.get(preciptype, preciptype)))
                    or ""
                )
                + (
                    precipaccumulation
                    and _("\nSnowfall accumulation: {} {}").format(
                        precipaccumulation,
                        await self.get_localized_units(ctx, "accumulation"),
                    )
                    or ""
                ),
            )
            em.add_field(name=_("Moon phase"), value=await self.num_to_moon(data.moonPhase))
            pages.append(em)
        await menu(ctx, pages, DEFAULT_CONTROLS)

    async def get_units(self, ctx: commands.Context):
        return (
            await self.config.user(ctx.author).units()
            or (await self.config.guild(ctx.guild).units() if ctx.guild else None)
            or "si"
        )

    async def get_localized_units(self, ctx: commands.Context, units_type: str):
        """Get translated contextual units for type"""
        if not ctx.guild:
            return _(
                UNITS.get(await self.config.user(ctx.author).units(), UNITS["si"]).get(
                    units_type, "?"
                )
            )
        current_system = (
            await self.config.user(ctx.author).units()
            or await self.config.guild(ctx.guild).units()
        )
        return _(UNITS.get(current_system, {}).get(units_type, "?"))

    async def get_lang(self):
        """Get language for forecastio, based on current's bot language"""
        locale = get_locale()
        special_cases = {"lol-US": "x-pig-latin", "debugging": "en", "zh-TW": "zh-tw"}
        lang = special_cases.get(locale, locale[:2])
        if lang in FORECASTIO_SUPPORTED_LANGS:
            return lang
        return "en"

    async def wind_bearing_direction(self, bearing: int):
        """Returns direction based on wind bearing"""
        # https://github.com/pandabubblepants/forecastSMS/blob/e396d978e1ec47b5f3023ce13d5a5f55c57e4f6e/forecastSMS.py#L12-L16
        dirs = [
            _("N"),
            _("NNE"),
            _("NE"),
            _("ENE"),
            _("E"),
            _("ESE"),
            _("SE"),
            _("SSE"),
            _("S"),
            _("SSW"),
            _("SW"),
            _("WSW"),
            _("W"),
            _("WNW"),
            _("NW"),
            _("NNW"),
        ]
        return dirs[int((bearing / 22.5) + 0.5) % 16]

    async def num_to_moon(self, moonphase: float) -> str:
        """Converts lunation number to lunar phase emoji"""
        if moonphase == 0:
            return "\N{New Moon Symbol}"
        if 0 < moonphase < 0.25:
            return "\N{Waxing Crescent Moon Symbol}"
        if moonphase == 0.25:
            return "\N{First Quarter Moon Symbol}"
        if 0.25 < moonphase < 0.5:
            return "\N{Waxing Gibbous Moon Symbol}"
        if moonphase == 0.5:
            return "\N{First Quarter Moon Symbol}"
        if 0.5 < moonphase < 0.75:
            return "\N{Waning Gibbous Moon Symbol}"
        if moonphase == 0.75:
            return "\N{Last Quarter Moon Symbol}"
        if 0.75 < moonphase < 1:
            return "\N{Waning Crescent Moon Symbol}"
        if moonphase == 1:
            return "\N{Full Moon Symbol}"
        return str(moonphase)
