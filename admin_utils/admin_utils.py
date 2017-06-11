import aiohttp
import discord
from discord.ext import commands
from asyncio import sleep
from .utils import chat_formatting as chat
from .utils import checks
import urllib.parse as up
import json


class admin_utils:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.base_api_url = "https://discordapp.com/api/oauth2/authorize?"
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def __unload(self):
        self.session.close()

    # @commands.command(no_pm=True, pass_context=True)
    # @commands.has_permissions(ban_members=True)
    # async def ban(self, ctx, member: discord.Member, delete_messages: int = 1):
    #     """Bans a member"""
    #     await self.bot.ban(member, delete_message_days=delete_messages)
    #     await self.bot.say(
    #         "User `" + member.name + "` banned\n" + str(delete_messages) + " days of user's messages removed")

    # @commands.command(no_pm=True, pass_context=True, aliases=["hackban"])
    # @commands.has_permissions(ban_members=True)
    # async def xban(self, ctx, member_id: str, days: int = 1):
    #     """Bans member by id"""
    #     member = discord.utils.get(set(self.bot.get_all_members()), id=member_id)
    #     try:
    #         await self.bot.http.ban(member_id, ctx.message.server.id, days)
    #     except discord.Forbidden:
    #         await self.bot.say(chat.error("Can't ban `{}`. Insufficient permissions.".format(member_id)))
    #     except discord.NotFound:
    #         await self.bot.say(chat.error("User with id `{}` not found").format(member_id))
    #     else:
    #         if member:
    #             await self.bot.say("User {} now is banned on this server".format(member.name))
    #         else:
    #             await self.bot.say("User with id `{}` successfully banned".format(member_id))

    # @commands.command(no_pm=True, pass_context=True)
    # @commands.has_permissions(kick_members=True)
    # async def kick(self, ctx, member: discord.Member):
    #     """Kicks a member"""
    #     await self.bot.kick(member)
    #     await self.bot.say("User `" + member.name + "` kicked")

    @commands.command(no_pm=True, pass_context=True, aliases=["prune"])
    @checks.admin_or_permissions(kick_members=True)
    async def cleanup_users(self, ctx, days: int = 1):
        """Cleanup inactive server members"""
        if days > 30:
            await self.bot.say(
                chat.error("Due to Discord Restrictions, you cannot use more than 30 days for that cmd."))
            days = 30
        elif days == 0:
            await self.bot.say(chat.error("\"days\" arg cannot be an zero..."))
            days = 1
        to_kick = await self.bot.estimate_pruned_members(ctx.message.server, days=days)
        await self.bot.say(chat.warning("You about to kick **{}** inactive for **{}** days members from this server. "
                                        "Are you sure?\nTo agree, type \"yes\"".format(to_kick, days)))
        await sleep(1)  # otherwise wait_for_message will catch message-warning
        resp = await self.bot.wait_for_message(author=ctx.message.author, channel=ctx.message.channel)
        if resp.content.lower().strip() == "yes":
            cleanup = await self.bot.prune_members(ctx.message.server, days=days)
            await self.bot.say(chat.info("**{}**/**{}** inactive members removed.\n"
                                         "(They was inactive for **{}** days)".format(cleanup, to_kick, days)))
        else:
            await self.bot.say(chat.error("Inactive members cleanup canceled."))

    @commands.command(no_pm=True, pass_context=True)
    @commands.has_permissions(create_instant_invite=True)
    async def invite(self, ctx):
        """Creates a server invite"""
        server = ctx.message.server
        invite = await self.bot.create_invite(server)
        await self.bot.say(invite.url)

    @commands.command(no_pm=True, pass_context=True)
    @commands.has_permissions(manage_emojis=True)
    async def add_emoji(self, ctx, emoji_name: str, emoji_url: str):
        """[SELFBOT ONLY} Adds an emoji to server
        Requires proper permissions
        PNG/JPG only"""
        try:
            async with self.session.get(emoji_url) as r:  # from Red's owner.py
                data = await r.read()
            await self.bot.create_custom_emoji(server=ctx.message.server, name=emoji_name, image=data)
            await self.bot.say("Done.")
        except Exception as e:
            await self.bot.say("Failed: " + chat.inline(e))

    @commands.command(no_pm=True, pass_context=True)
    @commands.has_permissions(manage_nicknames=True)
    async def massnick(self, ctx, nickname: str):
        """Mass nicknames everyone on the server"""
        server = ctx.message.server
        counter = 0
        for user in server.members:
            # if user.nick is None:
            #     nickname = "{} {}".format(nickname, user.name)
            # else:
            #     nickname = "{} {}".format(nickname, user.nick)
            try:
                await self.bot.change_nickname(user, nickname)
            except discord.HTTPException:
                counter += 1
                continue
        await self.bot.say("Finished nicknaming server. {} nicknames could not be completed.".format(counter))

    @commands.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(manage_nicknames=True)
    async def resetnicks(self, ctx):
        server = ctx.message.server
        for user in server.members:
            try:
                await self.bot.change_nickname(user, nickname=None)
            except discord.HTTPException:
                continue
        await self.bot.say("Finished resetting server nicknames")

    @commands.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def addbot(self, ctx, oauth_url):  # From Squid-Plugins for Red-DiscordBot:
        # https://github.com/tekulvw/Squid-Plugins
        """[SELFBOT ONLY] Adds bot to current server

        Based on autoapprove cog from Squid-Plugins
        https://github.com/tekulvw/Squid-Plugins"""
        server = ctx.message.server

        key = self.bot.settings.token
        parsed = up.urlparse(oauth_url)
        queryattrs = up.parse_qs(parsed.query)
        queryattrs['client_id'] = int(queryattrs['client_id'][0])
        queryattrs['scope'] = queryattrs['scope'][0]
        queryattrs.pop('permissions', None)
        full_url = self.base_api_url + up.urlencode(queryattrs)
        status = await self.get_bot_api_response(full_url, key, server.id)
        if status < 400:
            await self.bot.say("Succeeded!")
        else:
            await self.bot.say("Failed, error code {}. ".format(status))

    async def get_bot_api_response(self, url, key, serverid):
        data = {"guild_id": serverid, "permissions": 1024, "authorize": True}
        data = json.dumps(data).encode('utf-8')
        headers = {'authorization': key, 'content-type': 'application/json'}
        async with self.session.post(url, data=data, headers=headers) as r:
            status = r.status
        return status


def setup(bot):
    bot.add_cog(F10_admin_utils(bot))
