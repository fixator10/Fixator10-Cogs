import os
from datetime import datetime

import aiohttp
import tabulate
from discord.ext import commands

from cogs.utils import chat_formatting as chat
from cogs.utils import checks
from cogs.utils.dataIO import dataIO


class Holidays:
    """Check holidays for this month"""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.config_file = "data/holidays/config.json"
        self.config = dataIO.load_json(self.config_file)

    def __unload(self):
        self.session.close()

    @commands.group(pass_context=True, invoke_without_command=True)
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def holidays(self, ctx: commands.Context, country: str,
                       month: int = int(datetime.now().strftime('%m')),
                       year: int = int(datetime.now().strftime('%Y'))):
        """Check holidays
        Country must be presented in ISO 3166-2 format (example: US; RU)"""
        if month > 12 or month < 1 or len(str(year)) != 4:
            await self.bot.send_cmd_help(ctx)
            return
        if "APIkey" not in self.config:
            await self.bot.say(chat.error("API key is not set. "
                                          "Use {}holidays setkey to set API key.".format(ctx.prefix)))
            return
        if not self.config["premiumkey"] \
                and month == int(datetime.now().strftime('%m')) or \
                year > int(datetime.now().strftime('%Y')) or \
                (year >= int(datetime.now().strftime('%Y')) and month > int(datetime.now().strftime('%m'))):
            year = int(datetime.now().strftime('%Y')) - 1
            await self.bot.say(chat.warning("This bot has set non-premium key, "
                                            "so current and upcoming holiday data is unavailable. "
                                            "Query year was set to {}".format(year)))
        async with self.session.get("https://holidayapi.com/v1/holidays", params={"key": self.config["APIkey"],
                                                                                  "year": year,
                                                                                  "country": country,
                                                                                  "month": month}) as data:
            response = await data.json()
            if response["status"] == 200:
                for num, holiday in enumerate(response["holidays"]):
                    response["holidays"][num]["public"] = \
                        str(response["holidays"][num]["public"]).replace("False", "❎").replace("True", "✅")
                for page in chat.pagify(tabulate.tabulate(response["holidays"],
                                                          headers={"name": "Name",
                                                                   "date": "Date",
                                                                   "observed": "Observed",
                                                                   "public": "Public"},
                                                          tablefmt="orgtbl")):
                    await self.bot.say(chat.box(page))
            elif response["status"] < 500:
                await self.bot.say(chat.error("Something went wrong... "
                                              "Server returned client error code {}. "
                                              "This is possibly cog error.\n"
                                              "{}").format(response["status"], chat.inline(response["error"])))
            else:
                await self.bot.say(chat.error("Something went wrong... Server returned server error code {}. "
                                              "Try again later.").format(response["status"]))

    @holidays.command(pass_context=True)
    @checks.is_owner()
    async def setkey(self, ctx, api_key: str):
        """Set API key for holidayapi.com"""
        async with self.session.get("https://holidayapi.com/v1/holidays", params={"key": api_key,
                                                                                  "year": 2038,
                                                                                  "country": "US"}) as data:
            response = await data.json()
        if response["status"] == 402:
            self.config["premiumkey"] = False
        elif response["status"] == 401:
            await self.bot.say(chat.error("Invalid API key. Get an API key on https://holidayapi.com."))
            return
        elif response["status"] == 200:
            self.config["premiumkey"] = True
        elif response["status"] < 500:
            await self.bot.say(chat.error("Something went wrong... "
                                          "Server returned client error code {}. "
                                          "This is possibly cog error.\n"
                                          "{}").format(response["status"], chat.inline(response["error"])))
            return
        else:
            await self.bot.say(chat.error("Something went wrong... Server returned server error code {}. "
                                          "Try again later.").format(response["status"]))
            return
        self.config["APIkey"] = api_key
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say(chat.info("New API key for holidayapi.com set"))


def check_folders():
    if not os.path.exists("data/holidays"):
        os.makedirs("data/holidays")


def check_files():
    system = {}
    f = "data/holidays/config.json"
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, system)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(Holidays(bot))
