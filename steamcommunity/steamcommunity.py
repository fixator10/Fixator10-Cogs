import os
from datetime import datetime

import discord
from discord.ext import commands
from valve.steam.api import interface

from cogs.utils import chat_formatting as chat
from cogs.utils.dataIO import dataIO


class SteamCommunity:
    """SteamCommunity commands"""

    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/steamcommunity/config.json"
        self.config = dataIO.load_json(self.config_file)
        self.steam = interface.API(key=self.config["apikey"])

    async def resolve_vanity_url(self, vanity_url: str):
        """Resolve vanity URL"""
        userapi = self.steam['ISteamUser']
        resolved = userapi.ResolveVanityURL(vanity_url)["response"]
        return resolved.get("steamid"), resolved.get("message")

    @commands.group(pass_context=True, aliases=["sc"])
    async def steamcommunity(self, ctx):
        """Show user profile info"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @steamcommunity.command(pass_context=True)
    async def apikey(self, ctx, apikey: str):
        """Set API key for Steam web API
        You can get it here: https://steamcommunity.com/dev/apikey"""
        self.config["apikey"] = apikey
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say(chat.info("API key Updated"))

    @steamcommunity.command(name="profile", pass_context=True, aliases=["p"])
    async def steamprofile(self, ctx, user: str):
        """Get steam user's steamcommunity profile"""
        if not user.isdigit():
            user, message = await self.resolve_vanity_url(user)
            if user is None:
                chat.error("Unable to resolve vanity ID: {}".format(message))
                return
        profile = SteamUser(self.config["apikey"], user)
        em = discord.Embed(title=profile.personaname,
                           description=profile.personastate,
                           url=profile.profileurl,
                           timestamp=datetime.fromtimestamp(profile.lastlogoff))
        if profile.gameid is not None:
            em.description = "In game: [{}](http://store.steampowered.com/app/{})" \
                .format(profile.gameextrainfo or "Unknown", profile.gameid)
        if profile.realname is not None:
            em.add_field(name="Real name", value=profile.realname or chat.inline("None"), inline=False)
        em.add_field(name="Level", value=profile.level or "0")
        if profile.country is not None:
            em.add_field(name="Country", value=":flag_" + profile.country.lower() + ":"
                                               or chat.inline("Unknown"))
        em.add_field(name="Visibility", value=profile.visibility)
        em.add_field(name="SteamID", value=str(await self.convert_community_id_to_steam_id(profile.steamid)))
        em.add_field(name="SteamID64", value=profile.steamid)
        em.set_image(url=profile.avatar184)
        em.set_footer(text="Powered by Steam | Last seen on",
                      icon_url='https://steamstore-a.akamaihd.net/public/shared/images/responsive/share_steam_logo.png')
        await self.bot.say(embed=em)

    async def convert_community_id_to_steam_id(self, communityID):
        # https://raw.githubusercontent.com/Moshferatu/Steam-ID-Converter/master/SteamIDConverter.py
        steamid = ["STEAM_0:"]
        steamid_last_part = int(communityID) - 76561197960265728
        if steamid_last_part % 2 == 0:
            steamid.append("0:")
        else:
            steamid.append("1:")
        steamid.append(str(steamid_last_part // 2))
        return "".join(steamid)


class SteamUser:
    """SteamCommunity profile"""

    def __init__(self, apikey: str, player_id: str):
        steam = interface.API(key=apikey)
        user = steam['ISteamUser']
        player = steam['IPlayerService']
        userdata = user.GetPlayerSummaries(player_id)["response"]["players"][0]
        personastates = {
            0: "Offline",
            1: "Online",
            2: "Busy",
            3: "Away",
            4: "Snooze",
            5: "Looking to trade",
            6: "Looking to play"
        }
        visibilites = {
            1: "Private",
            3: "Public"
        }

        self.steamid = userdata.get("steamid")
        self.personaname = userdata.get("personaname")
        self.profileurl = userdata.get("profileurl")
        self.avatar32 = userdata.get("avatar")
        self.avatar64 = userdata.get("avatarmedium")
        self.avatar184 = userdata.get("avatarfull")
        self.personastate = personastates[userdata.get("personastate", 0)]
        self.visibility = visibilites[userdata.get("communityvisibiltystate", 1)]
        self.hasprofile = True if userdata.get("profilestate") else False
        self.lastlogoff = userdata.get("lastlogoff")
        self.comments = userdata.get("commentpermission")

        self.realname = userdata.get("realname")
        self.clanid = userdata.get("primaryclanid")
        self.gameid = userdata.get("gameid")
        gameserver = userdata.get("gameserverip")
        self.gameserver = gameserver if gameserver != any(["0.0.0.0:0", None]) else None
        self.gameextrainfo = userdata.get("gameextrainfo")
        self.country = userdata.get("loccountrycode")
        self.state = userdata.get("locstatecode")
        self.cityid = userdata.get("loccityid")

        self.level = player.GetSteamLevel(player_id)["response"].get("playerlevel", 0)


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
