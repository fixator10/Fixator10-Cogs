from discord.ext import commands
import aiohttp
from datetime import datetime
from .utils import chat_formatting as chat
import tabulate


class Holidays:
    """Check holidays for this month"""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    @commands.command(pass_context=True)
    async def holidays(self, ctx, country_code: str):
        """Check holidays for this month
Available country codes:
1.    Angola    ago
2.    Australia    aus
3.    Austria    aut
4.    Belgium    bel
5.    Brazil    bra
6.    Canada    can
7.    China    chn
8.    Colombia    col
9.    Croatia    hrv
10.    Czech Republic    cze
11.    Denmark    dnk
12.    England    eng
13.    Estonia    est
14.    Finland    fin
15.    France    fra
16.    Germany    deu
17.    Greece            grc
18.    Hong Kong    hkg
19.    Hungary     hun
20.    Iceland    isl
21.    Ireland    irl
22.    Isle of Man    imn
23.    Israel    isr
24.    Italy             ita
25.    Japan    jpn
26.    Latvia    lva
27.    Lithuania    ltu
28.    Luxembourg    lux
29.    Mexico    mex
30.    Netherlands    nld
31.    New Zealand    nzl
34.    Poland    pol
35.    Portugal     prt
36.    Romania    rou
37.    Russia    rus
38.    Serbia    srb
39.    Slovakia    svk
40.    Slovenia    svn
41.    South Africa    zaf
42.    South Korea    kor
43.    Scotland      sct
44.    Sweden    swe
45.    Ukraine    ukr
46.    United States of America    usa
47.    Wales    wls"""
        month = datetime.now().strftime('%m')
        year = datetime.now().strftime('%Y')
        try:
            async with self.session.get('http://kayaposoft.com/enrico/json/v1.0/'
                                        '?action=getPublicHolidaysForMonth'
                                        '&month={}&year={}&country={}'.format(month, year, country_code)) as data:
                data = await data.json()
                try:
                    data[0]["date"] = "{}.{}.{}"\
                        .format(data[0]["date"]["day"], data[0]["date"]["month"], data[0]["date"]["year"])
                except:
                    pass
                await self.bot.say(chat.box(tabulate.tabulate(data, headers={"date": "Date",
                                                                             "localName": "Name",
                                                                             "englishName": "Name (ENG)"},
                                                              tablefmt="fancy_grid")))
        except Exception as e:
            await self.bot.say(chat.error("Unable to find any holidays.\nAn error has been occurred: "+chat.inline(e)))


def setup(bot):
    bot.add_cog(Holidays(bot))
