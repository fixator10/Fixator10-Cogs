import os
from datetime import datetime

import discord
from discord.ext import commands
from valve.steam.api import interface
from valve.steam.id import SteamID

from cogs.utils import chat_formatting as chat
from cogs.utils import checks
from cogs.utils.dataIO import dataIO


def bool_emojify(bool_var: bool) -> str:
    return "✔" if bool_var else "❌"


class SteamCommunity:
    """SteamCommunity commands"""

    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/steamcommunity/config.json"
        self.config = dataIO.load_json(self.config_file)
        self.steam = interface.API(key=self.config["apikey"])

    def check_api(self):
        if "ISteamUser" in list(self.steam._interfaces.keys()):
            return True
        return False

    async def resolve_vanity_url(self, vanity_url: str):
        """Resolve vanity URL"""
        userapi = self.steam['ISteamUser']
        resolved = userapi.ResolveVanityURL(vanity_url)["response"]
        return resolved.get("steamid"), resolved.get("message")

    @commands.group(pass_context=True, aliases=["sc"])
    async def steamcommunity(self, ctx):
        """Steamcommunity commands"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @steamcommunity.command(pass_context=True)
    @checks.is_owner()
    async def apikey(self, ctx, apikey: str):
        """Set API key for Steam web API
        You can get it here: https://steamcommunity.com/dev/apikey"""
        self.config["apikey"] = apikey
        self.steam = interface.API(key=self.config["apikey"])
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say(chat.info("API key Updated"))

    @steamcommunity.command(name="profile", pass_context=True, aliases=["p"])
    async def steamprofile(self, ctx, steamid: str):
        """Get steam user's steamcommunity profile"""
        if not ctx.message.channel.permissions_for(ctx.message.server.me).embed_links:
            await self.bot.say(chat.error("This command requires enabled embeds.\n"
                                          "Ask admins of server to enable embeds for me in this channel and try again"))
            return
        if not self.check_api():
            await self.bot.say(chat.error("Steam web API key not set or it is incorrect.\n"
                                          "Ask owner of the bot to use "
                                          "`{}sc apikey` to setup API key".format(ctx.prefix)))
            return
        if not steamid.isdigit():
            if steamid.startswith("STEAM_0:"):
                steamid = SteamID.from_text(steamid).as_64()
            else:
                steamid, message = await self.resolve_vanity_url(steamid)
                if steamid is None:
                    await self.bot.say(chat.error("Unable to resolve vanity ID: {}".format(message)))
                    return
        try:
            profile = SteamUser(self.config["apikey"], steamid)
        except IndexError:
            await self.bot.say(chat.error("Unable to get profile for {}. "
                                          "Check your input or try again later.".format(steamid)))
            return
        em = discord.Embed(title=profile.personaname,
                           description=profile.personastate(),
                           url=profile.profileurl,
                           timestamp=datetime.fromtimestamp(profile.lastlogoff),
                           color=profile.personastatecolor)
        if profile.gameid:
            em.description = "In game: [{}](http://store.steampowered.com/app/{})" \
                .format(profile.gameextrainfo or "Unknown", profile.gameid)
            if profile.gameserver:
                em.description += " on server {}".format(profile.gameserver)
            if profile.shared_by:
                em.description += "\nFamily Shared by {}" \
                    .format(SteamUser(self.config["apikey"], profile.shared_by).personaname)
        if profile.realname:
            em.add_field(name="Real name", value=profile.realname, inline=False)
        em.add_field(name="Level", value=profile.level or "0")
        if profile.country:
            em.add_field(name="Country", value=":flag_{}:".format(profile.country.lower()))
        em.add_field(name="Visibility", value=profile.visibility)
        em.add_field(name="SteamID", value=profile.steamid)
        em.add_field(name="SteamID64", value=profile.steamid64)
        em.add_field(name="Community bans", value="\u200b", inline=False)
        em.add_field(name="Community Banned", value=bool_emojify(profile.communitybanned))
        em.add_field(name="VAC bans", value="VAC BANNED ({} bans, {} since last ban)"
                     .format(profile.VACbans, profile.sincelastban) if profile.VACbanned else bool_emojify(False))
        em.add_field(name="Game bans", value="{} game bans".format(profile.gamebans or "No"))
        em.add_field(name="Economy ban", value=profile.economyban.capitalize() if profile.economyban else "Not banned")
        em.set_thumbnail(url=profile.avatar184)
        em.set_footer(text="Powered by Steam | Last seen on",
                      icon_url='https://steamstore-a.akamaihd.net/public/shared/images/responsive/share_steam_logo.png')
        await self.bot.say(embed=em)


class SteamUser:
    """SteamCommunity profile"""

    def __init__(self, apikey: str, player_id: str):
        self._steam = interface.API(key=apikey)
        self._user = self._steam['ISteamUser']
        self._player = self._steam['IPlayerService']
        self._userdata = self._user.GetPlayerSummaries(player_id)["response"]["players"][0]
        self._bandata = self._user.GetPlayerBans(player_id)["players"][0]
        self._personastate = self._userdata.get("personastate", 0)
        visibilites = {
            1: "Private",
            2: "Friends only",
            3: "Public",  # Friends of friends
            4: "Users only",
            5: "Public"
        }

        self.steamid64 = self._userdata.get("steamid")
        self.personaname = self._userdata.get("personaname")
        self.profileurl = self._userdata.get("profileurl")
        self.avatar32 = self._userdata.get("avatar")
        self.avatar64 = self._userdata.get("avatarmedium")
        self.avatar184 = self._userdata.get("avatarfull")
        self.visibility = visibilites[self._userdata.get("communityvisibilitystate", 1)]
        self.hasprofile = True if self._userdata.get("profilestate") else False
        self.lastlogoff = self._userdata.get("lastlogoff")
        self.comments = self._userdata.get("commentpermission")

        self.realname = self._userdata.get("realname")
        self.clanid = self._userdata.get("primaryclanid")
        self.gameid = self._userdata.get("gameid")
        gameserver = self._userdata.get("gameserverip")
        self.gameserver = gameserver if gameserver != any(["0.0.0.0:0", None]) else None
        self.gameextrainfo = self._userdata.get("gameextrainfo")
        self.country = self._userdata.get("loccountrycode")
        self.state = self._userdata.get("locstatecode")
        self.cityid = self._userdata.get("loccityid")

        self.level = self._player.GetSteamLevel(player_id)["response"].get("player_level", 0)
        self.shared_by = self._player.IsPlayingSharedGame(player_id, self.gameid)["response"].get("lender_steamid")

        self.communitybanned = self._bandata.get("CommunityBanned")
        self.VACbanned = self._bandata.get("VACBanned")
        self.VACbans = self._bandata.get("NumberOfVACBans")
        self.sincelastban = self._bandata.get("DaysSinceLastBan")
        self.gamebans = self._bandata.get("NumberOfGameBans")
        economyban = self._bandata.get("EconomyBan")
        self.economyban = economyban if economyban != "none" else None

    def personastate(self, string: bool = True):
        """Get persona state
        :param string: Return string of state or id?"""
        stringnames = {
            0: "Offline",
            1: "Online",
            2: "Busy",
            3: "Away",
            4: "Snooze",
            5: "Looking to trade",
            6: "Looking to play"
        }
        if string:
            return stringnames[self._personastate]
        return self._personastate

    @property
    def personastatecolor(self):
        if self.gameextrainfo:
            return 0x90ba3c
        elif self._personastate > 0:
            return 0x57cbde
        return 0x898989

    @property
    def steamid(self):
        steamid = "STEAM_0:"
        steamid_last_part = int(self.steamid64) - 76561197960265728
        if steamid_last_part % 2 == 0:
            steamid += "0:"
        else:
            steamid += "1:"
        steamid += (str(steamid_last_part // 2))
        return steamid


def check_folders():
    if not os.path.exists("data/steamcommunity"):
        os.makedirs("data/steamcommunity")


def check_files():
    system = {"apikey": ""}

    f = "data/steamcommunity/config.json"
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, system)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(SteamCommunity(bot))
