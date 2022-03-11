from redbot.core import commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.predicates import MessagePredicate

from leveler.abc import MixinMeta

from .basecmd import DBConvertersBaseCMD


class MeeSix(MixinMeta):
    """Mee6 leveling converter"""

    lvlconvert = getattr(DBConvertersBaseCMD, "lvlconvert")

    @lvlconvert.group()
    @commands.guild_only()
    async def mee6(self, ctx):
        """Manage mee6 conversions."""

    @mee6.command(name="levels")
    @commands.guild_only()
    async def convertlevels(self, ctx, pages: int):
        """Convert Mee6 levels.
        Each page returns 999 users at most.
        This command must be run in a channel in the guild to be converted."""
        if await self.config.guild(ctx.guild).mentions():
            msg = (
                "{}, levelup mentions are on in this server.\n"
                "The bot will ping every user that will be leveled up through this process if you continue.\n"
                "Reply with `yes` if you want this conversion to continue.\n"
                "If not, reply with `no` and then run `{}lvladmin mention` "
                "to turn off mentions before running this command again."
            ).format(ctx.author.display_name, ctx.prefix)
            await ctx.send(msg)
            pred = MessagePredicate.yes_or_no(ctx)
            try:
                await self.bot.wait_for("message", check=pred, timeout=15)
            except TimeoutError:
                return await ctx.send("Timed out waiting for a response.")
            if pred.result is False:
                return await ctx.send("Command cancelled.")
        async with ctx.typing():
            failed = 0
            async for i in AsyncIter(range(pages)):
                async with self.session.get(
                    f"https://mee6.xyz/api/plugins/levels/leaderboard/{ctx.guild.id}?page={i}&limit=999"
                ) as r:

                    if r.status == 200:
                        data = await r.json()
                    else:
                        return await ctx.send("No data was found within the Mee6 API.")

                async for userdata in AsyncIter(data["players"]):
                    # _handle_levelup requires a Member
                    user = ctx.guild.get_member(int(userdata["id"]))

                    if not user:
                        failed += 1
                        continue

                    level = userdata["level"]
                    server = ctx.guild
                    channel = ctx.channel

                    # creates user if doesn't exist
                    await self._create_user(user, server)
                    userinfo = await self.db.users.find_one({"user_id": str(user.id)})

                    # get rid of old level exp
                    old_server_exp = 0
                    async for _i in AsyncIter(range(userinfo["servers"][str(server.id)]["level"])):
                        old_server_exp += await self._required_exp(_i)
                    userinfo["total_exp"] -= old_server_exp
                    userinfo["total_exp"] -= userinfo["servers"][str(server.id)]["current_exp"]

                    # add in new exp
                    total_exp = await self._level_exp(level)
                    userinfo["servers"][str(server.id)]["current_exp"] = 0
                    userinfo["servers"][str(server.id)]["level"] = level
                    userinfo["total_exp"] += total_exp

                    if userinfo["total_exp"] > 0:
                        await self.db.users.update_one(
                            {"user_id": str(user.id)},
                            {
                                "$set": {
                                    "servers.{}.level".format(server.id): level,
                                    "servers.{}.current_exp".format(server.id): 0,
                                    "total_exp": userinfo["total_exp"],
                                }
                            },
                        )
                        await self._handle_levelup(user, userinfo, server, channel)
            await ctx.send(f"{failed} users could not be found and were skipped.")

    @mee6.command(name="roles", aliases=["ranks"])
    @commands.guild_only()
    async def convertranks(self, ctx):
        """Convert Mee6 role rewards.
        This command must be run in a channel in the guild to be converted."""
        async with self.session.get(
            f"https://mee6.xyz/api/plugins/levels/leaderboard/{ctx.guild.id}"
        ) as r:
            if r.status == 200:
                data = await r.json()
            else:
                return await ctx.send("No data was found within the Mee6 API.")
        server = ctx.guild
        remove_role = None
        async for role in AsyncIter(data["role_rewards"]):
            role_id = int(role["role"]["id"])
            level = role["rank"]
            role_name = role["role"]["name"]

            role_obj = ctx.guild.get_role(role_id)
            if role_obj is None:
                await ctx.send("Please make sure the `{}` roles exist!".format(role_name))
            else:
                server_roles = await self.db.roles.find_one({"server_id": str(server.id)})
                if not server_roles:
                    new_server = {
                        "server_id": str(server.id),
                        "roles": {role_name: {"level": str(level), "remove_role": remove_role}},
                    }
                    await self.db.roles.insert_one(new_server)
                else:
                    if role_name not in server_roles["roles"]:
                        server_roles["roles"][role_name] = {}

                    server_roles["roles"][role_name]["level"] = str(level)
                    server_roles["roles"][role_name]["remove_role"] = remove_role
                    await self.db.roles.update_one(
                        {"server_id": str(server.id)}, {"$set": {"roles": server_roles["roles"]}}
                    )

                await ctx.send(
                    "The `{}` role has been linked to level `{}`".format(role_name, level)
                )
