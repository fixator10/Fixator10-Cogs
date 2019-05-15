from datetime import datetime
from functools import partial
from socket import gethostbyname_ex

import discord
import valve.source.a2s
from redbot.core import checks
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from valve.steam.api import interface

from .steamuser import SteamUser


def bool_emojify(bool_var: bool) -> str:
    return "✅" if bool_var else "❌"


def check_api(ctx):
    """Is API ready?"""
    if "ISteamUser" in list(ctx.cog.steam._interfaces.keys()):
        return True
    return False


def check_not_api(ctx):
    """Opposite to check_api(ctx)"""
    return not check_api(ctx)


_ = Translator("SteamCommunity", __file__)


@cog_i18n(_)
class SteamCommunity(commands.Cog):
    """SteamCommunity commands"""

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot

    # noinspection PyAttributeOutsideInit
    async def initialize(self):
        """Should be called straight after cog instantiation."""
        self.apikeys = await self.bot.db.api_tokens.get_raw(
            "steam", default={"web": None}
        )
        self.steam = await self.bot.loop.run_in_executor(
            None, partial(interface.API, key=self.apikeys["web"])
        )

    async def validate_ip(self, s):
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

    @commands.group(aliases=["sc"])
    async def steamcommunity(self, ctx):
        """SteamCommunity commands"""
        pass

    @steamcommunity.command()
    @commands.check(check_not_api)
    @checks.is_owner()
    async def apikey(self, ctx):
        """Set API key for Steam Web API"""
        await self.initialize()
        if "ISteamUser" in list(self.steam._interfaces.keys()):
            await ctx.tick()
            return
        message = _(
            "To get Steam Web API key:\n"
            "1. Login to your Steam account\n"
            "2. Visit [Register Steam Web API Key](https://steamcommunity.com/dev/apikey) page\n"
            "3. Enter any domain name (e.g. `localhost`)\n"
            '4. You will now see "Key" field\n'
            "5. Use `{}set api steam web,<your_apikey>`\n"
            "6. Use this command again\n\n"
            "Note: These tokens are sensitive and should only be used in a private channel\n"
            "or in DM with the bot."
        ).format(ctx.prefix)
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
            timestamp=datetime.fromtimestamp(profile.lastlogoff),
            color=profile.personastatecolor,
        )
        if profile.gameid:
            em.description = _(
                "In game: [{}](http://store.steampowered.com/app/{})"
            ).format(profile.gameextrainfo or "Unknown", profile.gameid)
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
            em.add_field(
                name=_("Country"), value=":flag_{}:".format(profile.country.lower())
            )
        em.add_field(name=_("Visibility"), value=profile.visibility)
        if profile.createdat:
            em.add_field(
                name=_("Created at"),
                value=datetime.utcfromtimestamp(profile.createdat).strftime(
                    _("%d.%m.%Y %H:%M:%S")
                ),
            )
        em.add_field(
            name="SteamID", value="{}\n{}".format(profile.steamid, profile.sid3)
        )
        em.add_field(name="SteamID64", value=profile.steamid64)
        if any([profile.VACbanned, profile.gamebans]):
            bansdescription = _("Days since last ban: {}").format(profile.sincelastban)
        elif any([profile.communitybanned, profile.economyban]):
            bansdescription = _("Has one or more bans:")
        else:
            bansdescription = _("No bans on record")
        em.add_field(name=_("🛡 Bans"), value=bansdescription, inline=False)
        em.add_field(
            name=_("Community ban"), value=bool_emojify(profile.communitybanned)
        )
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
            value=_("{} game bans").format(profile.gamebans)
            if profile.gamebans
            else "❌",
        )
        em.set_thumbnail(url=profile.avatar184)
        em.set_footer(
            text=_("Powered by Steam • Last seen on"),
            icon_url="https://steamstore-a.akamaihd.net/public/shared/images/responsive/share_steam_logo.png",
        )
        await ctx.send(embed=em)

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

        if not await self.validate_ip(str(servercheck)):
            await ctx.send_help()
            return

        try:
            server = await self.bot.loop.run_in_executor(
                None, valve.source.a2s.ServerQuerier, serverc
            )
            info = server.info()
            server.close()

        except valve.source.a2s.NoResponseError:
            await ctx.send(
                chat.error(
                    _(
                        "Could not fetch Server or the Server is not on the Steam masterlist"
                    )
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
            em.add_field(
                name=_("Players"), value="{}/{}\n".format(playernumber, maxplayers)
            )

        await ctx.send(embed=em)
