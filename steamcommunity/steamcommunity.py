from datetime import datetime

import discord
from redbot.core import checks
from redbot.core import commands
from redbot.core.utils import chat_formatting as chat
from valve.steam.api import interface

from .converters import SteamID
from .steamuser import SteamUser


def bool_emojify(bool_var: bool) -> str:
    return "✔" if bool_var else "❌"


def check_api(ctx):
    """Is API ready?"""
    if "ISteamUser" in list(ctx.cog.steam._interfaces.keys()):
        return True
    return False


def _check_api(ctx):
    """Opposite to check_api(ctx)"""
    return not check_api(ctx)


class SteamCommunity(commands.Cog):
    """SteamCommunity commands"""

    def __init__(self, bot):
        self.bot = bot

    async def initialize(self):
        """Should be called straight after cog instantiation."""
        self.apikeys = await self.bot.db.api_tokens.get_raw("steam", default={"web": None})
        self.steam = interface.API(key=self.apikeys["web"])

    @commands.group(aliases=["sc"])
    async def steamcommunity(self, ctx):
        """SteamCommunity commands"""
        pass

    @steamcommunity.command()
    @commands.check(_check_api)
    @checks.is_owner()
    async def apikey(self, ctx):
        """Set API key for Steam Web API"""
        await self.initialize()
        if "ISteamUser" in list(self.steam._interfaces.keys()):
            await ctx.tick()
            return
        message = (
            "To get Steam Web API key:\n"
            "1. Login to your Steam account\n"
            "2. Visit [Register Steam Web API Key](https://steamcommunity.com/dev/apikey) page\n"
            "3. Enter any domain name (e.g. `localhost`)\n"
            "4. You will now see \"Key\" field\n"
            "5. Use `{}set api steam web,<your_apikey>`\n"
            "6. Use this command again\n\n"
            "Note: These tokens are sensitive and should only be used in a private channel\n"
            "or in DM with the bot.".format(ctx.prefix)
        )
        await ctx.maybe_send_embed(message)

    @steamcommunity.command(name="profile", aliases=["p"])
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.check(check_api)
    async def steamprofile(self, ctx, steamid: SteamID):
        """Get steam user's steamcommunity profile"""
        try:
            profile = SteamUser(self.steam, steamid)
        except IndexError:
            await ctx.send(chat.error("Unable to get profile for {}. "
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
                em.description += "\nFamily Shared by [{}]({})" \
                    .format(profile.shared_by.personaname, profile.shared_by.profileurl)
        if profile.realname:
            em.add_field(name="Real name", value=profile.realname, inline=False)
        em.add_field(name="Level", value=profile.level or "0")
        if profile.country:
            em.add_field(name="Country", value=":flag_{}:".format(profile.country.lower()))
        em.add_field(name="Visibility", value=profile.visibility)
        if profile.createdat:
            em.add_field(name="Created at",
                         value=datetime.utcfromtimestamp(profile.createdat).strftime("%d.%m.%Y %H:%M:%S"))
        em.add_field(name="SteamID", value="{}\n{}".format(profile.steamid, profile.sid3))
        em.add_field(name="SteamID64", value=profile.steamid64)
        if any([profile.VACbanned, profile.gamebans]):
            bansdescription = "Days since last ban: {}".format(profile.sincelastban)
        elif any([profile.communitybanned, profile.economyban]):
            bansdescription = "Has one or more bans:"
        else:
            bansdescription = "No bans on record"
        em.add_field(name="🛡 Bans", value=bansdescription, inline=False)
        em.add_field(name="Community ban", value=bool_emojify(profile.communitybanned))
        em.add_field(name="Economy ban", value=profile.economyban.capitalize() if profile.economyban else "❌")
        em.add_field(name="VAC bans", value="{} VAC bans".format(profile.VACbans) if profile.VACbans else "❌")
        em.add_field(name="Game bans", value="{} game bans".format(profile.gamebans) if profile.gamebans else "❌")
        em.set_thumbnail(url=profile.avatar184)
        em.set_footer(text="Powered by Steam • Last seen on",
                      icon_url='https://steamstore-a.akamaihd.net/public/shared/images/responsive/share_steam_logo.png')
        await ctx.send(embed=em)
