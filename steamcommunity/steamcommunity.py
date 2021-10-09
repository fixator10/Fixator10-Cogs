from collections import namedtuple
from contextlib import suppress
from datetime import datetime
from functools import partial
from io import BytesIO
from os import path
from socket import gethostbyname_ex
from time import time
from warnings import filterwarnings

import aiohttp
import discord
import valve.source.a2s
from fixcogsutils.dpy_future import get_markdown_timestamp
from fixcogsutils.formatting import bool_emojify
from redbot.core import commands
from redbot.core.data_manager import bundled_data_path
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from valve.steam.api import interface

with suppress(Exception):
    from matplotlib import pyplot, units as munits, dates as mdates, use as mpluse
    import numpy as np

from .steamuser import SteamUser

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json


USERAGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/88.0.4324.104 "
    "Safari/537.36"
)
LOAD_INDICATORS = ["\N{GREEN HEART}", "\N{YELLOW HEART}", "\N{BROKEN HEART}"]


def check_api(ctx):
    """Is API ready?"""
    return "ISteamUser" in list(ctx.cog.steam._interfaces.keys())


async def validate_ip(s):
    """Is IP address valid"""
    a = s.split(".")
    if len(a) != 4:
        return False
    for x in a:
        if not x.isdigit():
            return False
        i = int(x)
        if i < 0 or i > 255:
            return False
    return True


async def find_service(services: dict, service: str):
    """Find service from steamstat.us' service list"""
    Service = namedtuple("Service", ["id", "load", "text", "text_with_indicator"])
    for s in services:
        if s[0] == service:
            return Service(s[0], s[1], s[2], f"{LOAD_INDICATORS[s[1]]} {s[2]}")
    return Service("", "", "", "")


_ = Translator("SteamCommunity", __file__)

filterwarnings("ignore", category=FutureWarning, module=r"valve.")


@cog_i18n(_)
class SteamCommunity(commands.Cog):
    """SteamCommunity commands"""

    __version__ = "2.1.16"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.steam = None
        self.session = aiohttp.ClientSession(json_serialize=json.dumps)
        self.status_data = {"last_update": 0.0, "data": {}}

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def red_delete_data_for_user(self, **kwargs):
        return

    async def initialize(self):
        """Should be called straight after cog instantiation."""
        apikeys = await self.bot.get_shared_api_tokens("steam")
        self.steam = await self.asyncify(interface.API, key=apikeys.get("web"))

    async def asyncify(self, func, *args, **kwargs):
        """Run func in executor"""
        return await self.bot.loop.run_in_executor(None, partial(func, *args, **kwargs))

    @commands.group(aliases=["sc"])
    async def steamcommunity(self, ctx):
        """SteamCommunity commands"""
        pass

    @steamcommunity.command()
    @commands.is_owner()
    async def apikey(self, ctx):
        """Set API key for Steam Web API"""
        message = _(
            "To get Steam Web API key:\n"
            "1. Login to your Steam account\n"
            "2. Visit [Register Steam Web API Key](https://steamcommunity.com/dev/apikey) page\n"
            "3. Enter any domain name (e.g. `localhost`)\n"
            '4. You will now see "Key" field\n'
            "5. Use `{}set api steam web <your_apikey>`\n"
            "Note: These tokens are sensitive and should only be used in a private channel\n"
            "or in DM with the bot."
        ).format(ctx.clean_prefix)
        await ctx.maybe_send_embed(message)

    @steamcommunity.command(name="profile", aliases=["p"])
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.check(check_api)
    async def steamprofile(self, ctx, profile: SteamUser):
        """Get steam user's steamcommunity profile"""
        em = discord.Embed(
            title=profile.personaname,
            description=profile.personastate(),
            url=profile.profileurl,
            timestamp=datetime.utcfromtimestamp(profile.lastlogoff)
            if profile.lastlogoff
            else discord.Embed.Empty,
            color=profile.personastatecolor,
        )
        if profile.gameid:
            em.description = _("In game: [{}](http://store.steampowered.com/app/{})").format(
                profile.gameextrainfo or "Unknown", profile.gameid
            )
            if profile.gameserver:
                em.description += _(" on server {}").format(profile.gameserver)
            if profile.shared_by:
                em.description += _("\nFamily Shared by [{}]({})").format(
                    profile.shared_by.personaname, profile.shared_by.profileurl
                )
        if profile.realname:
            em.add_field(name=_("Real name"), value=profile.realname, inline=False)
        em.add_field(name=_("Level"), value=profile.level or "0")
        if profile.country:
            em.add_field(name=_("Country"), value=":flag_{}:".format(profile.country.lower()))
        em.add_field(name=_("Visibility"), value=profile.visibility)
        if profile.createdat:
            em.add_field(
                name=_("Created at"),
                value=get_markdown_timestamp(datetime.utcfromtimestamp(profile.createdat)),
            )
        em.add_field(name="SteamID", value="{}\n{}".format(profile.steamid, profile.sid3))
        em.add_field(name="SteamID64", value=profile.steamid64)
        if any([profile.VACbanned, profile.gamebans]):
            bansdescription = _("Days since last ban: {}").format(profile.sincelastban)
        elif any([profile.communitybanned, profile.economyban]):
            bansdescription = _("Has one or more bans:")
        else:
            bansdescription = _("No bans on record")
        em.add_field(name=_("🛡 Bans"), value=bansdescription, inline=False)
        em.add_field(name=_("Community ban"), value=bool_emojify(profile.communitybanned))
        em.add_field(
            name=_("Economy ban"),
            value=profile.economyban.capitalize() if profile.economyban else "❌",
        )
        em.add_field(
            name=_("VAC bans"),
            value=_("{} VAC bans").format(profile.VACbans) if profile.VACbans else "❌",
        )
        em.add_field(
            name=_("Game bans"),
            value=_("{} game bans").format(profile.gamebans) if profile.gamebans else "❌",
        )
        em.set_thumbnail(url=profile.avatar184)
        footer = [_("Powered by Steam")]
        if profile.lastlogoff:
            footer.append(_("Last seen on"))
        em.set_footer(
            text=" • ".join(footer),
            icon_url="https://steamstore-a.akamaihd.net/public/shared/images/responsive/share_steam_logo.png",
        )
        await ctx.send(embed=em)

    @steamcommunity.command(name="status")
    @commands.cooldown(1, 45, commands.BucketType.guild)
    @commands.bot_has_permissions(embed_links=True)
    @commands.max_concurrency(1, commands.BucketType.user)
    async def steamstatus(self, ctx):
        """Get status of steam services"""
        async with ctx.typing():
            if time() - self.status_data["last_update"] >= 45:
                try:
                    async with self.session.get(
                        "https://vortigaunt.steamstat.us/not_an_api.json",
                        headers={"referer": "https://steamstat.us/", "User-Agent": USERAGENT},
                        raise_for_status=True,
                    ) as gravity:
                        data = await gravity.json(loads=json.loads)
                        self.status_data["data"] = data
                        self.status_data["last_update"] = time()
                except aiohttp.ClientResponseError as e:
                    await ctx.send(
                        chat.error(
                            _("Unable to get data from steamstat.us: {} ({})").format(
                                e.status, e.message
                            )
                        )
                    )
                    return
                except aiohttp.ClientError as e:
                    await ctx.send(
                        chat.error(_("Unable to get data from steamstat.us: {}").format(e))
                    )
                    return
            else:
                data = self.status_data["data"]
        services = data.get("services", {})
        graph = data.get("graph")
        em = discord.Embed(
            title=_("Steam Status"),
            url="https://steamstat.us",
            color=await ctx.embed_color(),
            timestamp=datetime.utcfromtimestamp(data.get("time", 0)),
        )
        em.description = _(
            "**Online**: {}\n"
            "**In-game**: {}\n"
            "**Store**: {}\n"
            "**Community**: {}\n"
            "**Web API**: {}\n"
            "**Steam Connection Managers**: {}\n"
            "**SteamDB.info database**: {}"
        ).format(
            (await find_service(services, "online")).text_with_indicator,
            (await find_service(services, "ingame")).text_with_indicator,
            (await find_service(services, "store")).text_with_indicator,
            (await find_service(services, "community")).text_with_indicator,
            (await find_service(services, "webapi")).text_with_indicator,
            (await find_service(services, "cms")).text_with_indicator,
            (await find_service(services, "database")).text_with_indicator,
        )
        em.add_field(
            name=_("Games"),
            value=_(
                "**TF2 Game Coordinator**: {}\n"
                "**Dota 2 Game Coordinator**: {}\n"
                "**Underlords Game Coordinator**: {}\n"
                "**Artifact Game Coordinator**: {}\n"
                "**CS:GO Game Coordinator**: {}\n"
                "**CS:GO Sessions Logon**: {}\n"
                "**CS:GO Player Inventories**: {}\n"
                "**CS:GO Matchmaking Scheduler**: {}\n"
            ).format(
                (await find_service(services, "tf2")).text_with_indicator,
                (await find_service(services, "dota2")).text_with_indicator,
                (await find_service(services, "underlords")).text_with_indicator,
                (await find_service(services, "artifact")).text_with_indicator,
                (await find_service(services, "csgo")).text_with_indicator,
                (await find_service(services, "csgo_sessions")).text_with_indicator,
                (await find_service(services, "csgo_community")).text_with_indicator,
                (await find_service(services, "csgo_mm_scheduler")).text_with_indicator,
            ),
        )
        graph_file = None
        if all(lib in globals().keys() for lib in ["pyplot", "np"]):
            graph_file = await self.asyncify(self.gen_steam_cm_graph, graph)
            graph_file = discord.File(graph_file, filename="CMgraph.png")
            em.set_image(url="attachment://CMgraph.png")
        # TODO: Regions?
        await ctx.send(embed=em, file=graph_file)
        if graph_file:
            graph_file.close()

    @commands.command(aliases=["gameserver"])
    async def getserver(self, ctx, serverip: str):
        """Get info about a gameserver"""

        if ":" not in serverip:
            serverip += ":27015"

        serverc = serverip.split(":")
        if not serverc[0][0].isdigit():
            try:
                ip = gethostbyname_ex(serverc[0])[2][0]
            except Exception as e:
                await ctx.send(_("The specified domain is not valid: {}").format(e))
                return
            servercheck = ip
            serverc = [str(ip), int(serverc[1])]
        else:
            servercheck = serverc[0]
            serverc = [str(serverc[0]), int(serverc[1])]
        serverc = tuple(serverc)

        if not await validate_ip(str(servercheck)):
            await ctx.send_help()
            return

        async with ctx.typing():
            try:
                server = await self.asyncify(valve.source.a2s.ServerQuerier, serverc)
                info = server.info()
                server.close()

            except valve.source.a2s.NoResponseError:
                await ctx.send(
                    chat.error(
                        _("Could not fetch Server or the Server is not on the Steam masterlist")
                    )
                )
                return
            except Exception as e:
                await ctx.send(chat.error(_("An Error has been occurred: {}").format(e)))
                return

        _map = info.values["map"]

        if _map.lower().startswith("workshop"):
            link = "https://steamcommunity.com/sharedfiles/filedetails/?id={}".format(
                _map.split("/")[1]
            )
            _map = "{} [(Workshop map)]({})".format(_map.split("/")[2], link)

        game = info.values["folder"]
        gameid = info.values["app_id"]
        gamemode = info.values["game"]

        servername = info.values["server_name"].strip()
        servertype = str(info.values["server_type"])

        playernumber = str(info.values["player_count"] - info.values["bot_count"])
        botnumber = int(info.values["bot_count"])
        maxplayers = str(info.values["max_players"])

        os = str(info.values["platform"])
        version = info.values["version"]

        em = discord.Embed(colour=await ctx.embed_color())
        em.add_field(
            name=_("Game"),
            value=f"[{game}](http://store.steampowered.com/app/{gameid})",
        )
        em.add_field(name=_("Gamemode"), value=gamemode)
        em.add_field(name=_("Server name"), value=servername, inline=False)
        em.add_field(name=_("Map"), value=_map, inline=False)
        em.add_field(name="IP", value=serverc[0])
        em.add_field(name=_("Operating System"), value=os)
        em.add_field(name=_("Server type"), value=servertype)
        em.add_field(name=_("Version"), value=version)
        em.add_field(name="VAC", value=bool_emojify(bool(info.values["vac_enabled"])))
        em.add_field(
            name=_("Password"),
            value=bool_emojify(bool(info.values["password_protected"])),
        )
        if botnumber:
            em.add_field(
                name=_("Players"),
                value=_("{}/{}\nBots: {}").format(playernumber, maxplayers, botnumber),
            )
        else:
            em.add_field(name=_("Players"), value="{}/{}\n".format(playernumber, maxplayers))

        await ctx.send(embed=em)

    @commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name, api_tokens):
        if service_name == "steam":
            self.steam = await self.asyncify(interface.API, key=api_tokens.get("web"))

    def gen_steam_cm_graph(self, graphdata: dict):
        """Make an graph for connection managers"""
        mpluse("Agg")
        formats = [
            "%y",  # ticks are mostly years
            "%b",  # ticks are mostly months
            "%d",  # ticks are mostly days
            "%H:%M",  # hrs
            "%H:%M",  # min
            "%S.%f",  # secs
        ]
        zero_formats = [""] + formats[:-1]
        zero_formats[3] = "%d-%b"
        offset_formats = [
            "",
            "%Y",
            "%b %Y",
            "%d %b %Y",
            "%d %b %Y",
            "%d %b %Y %H:%M",
        ]
        munits.registry[datetime] = mdates.ConciseDateConverter(
            formats=formats, zero_formats=zero_formats, offset_formats=offset_formats
        )
        cur = graphdata["start"]
        x = []
        for _ in range(len(graphdata["data"])):
            cur += graphdata["step"]
            x.append(cur)
        x = [datetime.utcfromtimestamp(_x / 1000) for _x in x]
        y = graphdata["data"]
        graphfile = BytesIO()
        with pyplot.style.context(path.join(bundled_data_path(self), "discord.mplstyle")):
            fig, ax = pyplot.subplots()
            ax.plot(x, y)
            ax.set_ylim(bottom=0)
            ax.grid()
            ax.set(xlabel="Date", ylabel="%", title="Steam Connection Managers")
            ax.set_yticks(np.arange(0, 100, 5))
            fig.savefig(graphfile)
            pyplot.close(fig)
        graphfile.seek(0)
        return graphfile
