from redbot.core.commands import BadArgument
from redbot.core.commands import Converter
from valve.steam.id import SteamID


class SteamID(Converter):
    async def convert(self, ctx, argument) -> str:
        steam = ctx.cog.steam
        if "ISteamUser" not in list(steam._interfaces.keys()):
            raise BadArgument("ApiKey not set or incorrect.")
        userapi = steam['ISteamUser']
        if argument.startswith("http"):
            argument.strip("/")
            argument = argument.split("/")[-1]
        if argument.isdigit():
            id64 = argument
        else:
            if argument.startswith("STEAM_"):
                id64 = SteamID.from_text(argument).as_64()
            else:
                id64 = userapi.ResolveVanityURL(argument)["response"].get("steamid", "")
        if not id64.isnumeric():
            raise BadArgument("User with SteamID {} not found.".format(argument))
        return id64
