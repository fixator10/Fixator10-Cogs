import forecastio
import geocoder
import discord
import datetime
import os
from .utils.dataIO import dataIO
from .utils import chat_formatting as chat
from .utils import checks
from discord.ext import commands


def xstr(s):
    if s is None:
        return ''
    return str(s)


dictionary = {
    "clear-day": ":sunny:",
    "clear-night": ":night_with_stars:",
    "rain": ":cloud_rain:",
    "snow": ":cloud_snow:",
    "sleet": ":snowflake:",
    "wind": ":wind_blowing_face: ",
    "fog": ":foggy:",
    "cloudy": ":white_sun_cloud:",
    "partly-cloudy-day": ":white_sun_small_cloud:",
    "partly-cloudy-night": ":night_with_stars:",
    "": ":sunny:"
}


class Weather:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_file = "data/weather/config.json"
        self.config = dataIO.load_json(self.config_file)
        self.apikey = self.config["dark_sky_api_key"]

    @commands.command(pass_context=True)
    async def weather(self, ctx, place: str = None):
        """Shows weather in provided place"""
        if place is None:
            place = self.config["hometown"]
        g = geocoder.google(place)
        if len(g.latlng) == 0:
            await self.bot.say("Cannot find a place `" + place + "`")
            return
        forecast = forecastio.load_forecast(self.apikey, g.latlng[0], g.latlng[1], units="si")
        by_hour = forecast.currently()
        place = g.city_long + " | " + xstr(g.country_long)

        content = "Weather in " + place \
                  + ":\n" + by_hour.summary + "\n" + str(by_hour.temperature) + \
                  "˚C" + "\n" + dictionary.get(xstr(by_hour.icon))
        em = discord.Embed(description=content, colour=0xff0000, timestamp=by_hour.time)
        if ctx.message.channel.permissions_for(ctx.message.author).embed_links:
            await self.bot.say(embed=em)
        else:
            await self.bot.say(content)

    @commands.group(pass_context=True)
    @checks.is_owner()
    async def weather_set(self, ctx):
        """Set weather cog settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @weather_set.command()
    @checks.is_owner()
    async def api(self, *, apikey: str):
        """Set Weather apikey
        https://darksky.net/dev/"""
        self.config["dark_sky_api_key"] = apikey
        self.apikey = self.config["dark_sky_api_key"]
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say(chat.info("Apikey Updated"))

    @weather_set.command()
    @checks.is_owner()
    async def hometown(self, place: str):
        """Set default town for commands"""
        self.config["hometown"] = place
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say(chat.info("Bot's hometown now is \"{}\"".format(place)))

    @weather.error
    async def error(self, exception, ctx):
        await self.bot.say(chat.error("An error has been occured. Check your apikey, "
                                      "and set new with {}weather_set api").format(ctx.prefix))

    # @commands.command(pass_context=True)
    # async def time(self, ctx, place: str = None):
    #     if place is None:
    #         forecast = forecastio.load_forecast(self.apikey, "40.241495", "-75.283786", units="si")
    #         by_hour = forecast.currently()
    #         place = "Lansdale, PA"
    #     else:
    #         g = geocoder.google(place)
    #         if len(g.latlng) == 0:
    #             await self.bot.say("Cannot find a place " + place)
    #             return
    #         forecast = forecastio.load_forecast(self.apikey, g.latlng[0], g.latlng[1], units="si")
    #         by_hour = forecast.currently()
    #
    #     await self.bot.say("Time in " + place + " " + by_hour.time.timetz().isoformat())

    @commands.command(pass_context=True)
    async def forecast(self, ctx, place: str = None):
        """Shows 7 days forecast for provided place"""
        if place is None:
            place = self.config["hometown"]
        g = geocoder.google(place)
        if len(g.latlng) == 0:
            await self.bot.say("Cannot find a place `" + place + "`")
            return
        forecast = forecastio.load_forecast(self.apikey, g.latlng[0], g.latlng[1], units="si")
        by_hour = forecast.daily()
        place = g.city_long + " | " + xstr(g.country_long)

        content = "Weather in " + place + ":\n"
        for i in range(0, 6):
            content = content + \
                      "__***" + by_hour.data[i].time.strftime("%d/%m") + ":***__       " + \
                      xstr(by_hour.data[i].temperatureMin) + " - " + \
                      xstr(by_hour.data[i].temperatureMax) + "˚C       " \
                      + dictionary.get(xstr(by_hour.data[i].icon)) + "\n"
        em = discord.Embed(description=content, colour=0xff0000, timestamp=datetime.datetime.now())
        if ctx.message.channel.permissions_for(ctx.message.author).embed_links:
            await self.bot.say(embed=em)
        else:
            await self.bot.say(content)


def check_folders():
    if not os.path.exists("data/weather"):
        os.makedirs("data/weather")


def check_files():
    system = {"dark_sky_api_key": "",
              "hometown": "Pripyat"}

    f = "data/weather/config.json"
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, system)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(Weather(bot))
