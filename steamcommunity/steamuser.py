from valve.steam.api.interface import API


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
            1: "Private",
            2: "Friends only",
            3: "Public",  # Friends of friends
            4: "Users only",
            5: "Public",
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
            6: "Looking to play",
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
                return (
                    None
                )  # TODO: Find a better way do detect mods and other shit like that
            if int(sharedbyid) != 0:
                return SteamUser(self._steam, sharedbyid)
        return None

    @property
    def personastatecolor(self):
        if self.gameextrainfo:
            return 0x90BA3C
        elif self._personastate > 0:
            return 0x57CBDE
        return 0x898989
