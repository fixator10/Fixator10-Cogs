from redbot.core.commands import BadArgument
from redbot.core.i18n import Translator
from valve.steam.api.interface import API
from valve.steam.id import SteamID
from valve.steam.id import SteamIDError

_ = Translator("SteamCommunity", __file__)


class SteamUser:
    """SteamCommunity profile"""

    def __init__(self, steam: API, player_id: str):
        self._steam = steam
        self._user = self._steam["ISteamUser"]
        self._player = self._steam["IPlayerService"]
        self._userdata = self._user.GetPlayerSummaries(player_id)["response"][
            "players"
        ][0]
        self._bandata = self._user.GetPlayerBans(player_id)["players"][0]
        self._personastate = self._userdata.get("personastate", 0)
        visibilites = {
            1: _("Private"),
            2: _("Friends only"),
            3: _("Public"),  # Friends of friends
            4: _("Users only"),
            5: _("Public"),
        }
        acctypes = ["I", "U", "M", "G", "A", "P", "C", "g", "T", "", "a"]

        self.steamid64 = self._userdata.get("steamid")
        self.createdat = self._userdata.get("timecreated")
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

        self.level = self._player.GetSteamLevel(player_id)["response"].get(
            "player_level", 0
        )

        self.communitybanned = self._bandata.get("CommunityBanned")
        self.VACbanned = self._bandata.get("VACBanned")
        self.VACbans = self._bandata.get("NumberOfVACBans")
        self.sincelastban = self._bandata.get("DaysSinceLastBan")
        self.gamebans = self._bandata.get("NumberOfGameBans")
        economyban = self._bandata.get("EconomyBan")
        self.economyban = economyban if economyban != "none" else None

        self.iduniverse = int(self.steamid64) >> 56
        self.idpart = int(self.steamid64) & 0b1
        self.accountnumber = (
            int(self.steamid64) & 0b11111111111111111111111111111110
        ) >> 1
        self.accountid = int(self.steamid64) & 0b11111111111111111111111111111111
        self.idinstance = (
            int(self.steamid64) & 0b1111111111111111111100000000000000000000000000000000
        ) >> 32
        self.idtype = (
            int(self.steamid64)
            & 0b11110000000000000000000000000000000000000000000000000000
        ) >> 52

        self.steamid = "STEAM_{}:{}:{}".format(
            self.iduniverse, self.idpart, self.accountnumber
        )
        self.sid3 = "[{}:{}:{}]".format(
            acctypes[self.idtype], self.iduniverse, self.accountid
        )

    @classmethod
    async def convert(cls, ctx, argument):
        steam = ctx.cog.steam
        if "ISteamUser" not in list(steam._interfaces.keys()):
            raise BadArgument(_("ApiKey not set or incorrect."))
        userapi = steam["ISteamUser"]
        if argument.startswith("http"):
            argument = argument.strip("/").split("/")[-1]
        if argument.isdigit():
            id64 = argument
        else:
            if argument.startswith("STEAM_"):
                try:
                    id64 = SteamID.from_text(argument).as_64()
                except SteamIDError:
                    raise BadArgument(_("Incorrect SteamID32 provided."))
            else:
                id64 = userapi.ResolveVanityURL(argument)["response"].get("steamid", "")
        if not id64.isnumeric():
            raise BadArgument(_("User with SteamID {} not found.").format(argument))
        try:
            profile = await ctx.bot.loop.run_in_executor(
                None, SteamUser, steam, id64
            )
        except IndexError:
            raise BadArgument(
                _(
                    "Unable to get profile for {} ({}). "
                    "Check your input or try again later."
                ).format(argument, id64)
            )
        return profile

    def personastate(self, string: bool = True):
        """Get persona state
        :param string: Return string of state or id?"""
        stringnames = {
            0: _("Offline"),
            1: _("Online"),
            2: _("Busy"),
            3: _("Away"),
            4: _("Snooze"),
            5: _("Looking to trade"),
            6: _("Looking to play"),
        }
        if string:
            return stringnames[self._personastate]
        return self._personastate

    @property
    def shared_by(self):
        if self.gameid:
            try:
                sharedbyid = self._player.IsPlayingSharedGame(
                    self.gameid, self.steamid64
                )["response"].get("lender_steamid", 0)
            except ValueError:
                return None
            if int(sharedbyid) != 0:
                return SteamUser(self._steam, sharedbyid)
        return None

    @property
    def personastatecolor(self):
        if self.gameextrainfo:
            return 0x90BA3C
        if self._personastate > 0:
            return 0x57CBDE
        return 0x898989
