import discord
from redbot.core import bank, commands
from redbot.core.utils import chat_formatting as chat
from tabulate import tabulate

from ..abc import CompositeMetaClass, MixinMeta


class Profiles(MixinMeta, metaclass=CompositeMetaClass):
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="profile")
    @commands.guild_only()
    async def profile(self, ctx, *, user: discord.Member = None):
        """Displays a user profile."""
        if user is None:
            user = ctx.message.author
        if user.bot:
            ctx.command.reset_cooldown(ctx)
            await ctx.send_help()
            return
        channel = ctx.message.channel
        server = user.guild

        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        if await self.config.guild(ctx.guild).text_only():
            em = await self.profile_text(user, server, userinfo)
            await channel.send(embed=em)
        else:
            async with ctx.channel.typing():
                profile = await self.draw_profile(user, server)
                file = discord.File(profile, filename="profile.png")
                await channel.send(
                    "User profile for {}".format(user.mention),
                    file=file,
                    allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
                )
            profile.close()

    async def profile_text(self, user, server, userinfo):
        em = discord.Embed(colour=user.colour)
        em.add_field(name="Title:", value=userinfo["title"] or None)
        em.add_field(name="Reps:", value=userinfo["rep"])
        em.add_field(name="Global Rank:", value="#{}".format(await self._find_global_rank(user)))
        em.add_field(
            name="Server Rank:",
            value="#{}".format(await self._find_server_rank(user, server)),
        )
        em.add_field(
            name="Server Level:",
            value=format(userinfo["servers"][str(server.id)]["level"]),
        )
        em.add_field(name="Total Exp:", value=userinfo["total_exp"])
        em.add_field(name="Server Exp:", value=await self._find_server_exp(user, server))
        u_credits = await bank.get_balance(user)
        em.add_field(
            name="Credits:",
            value=f"{u_credits}{(await bank.get_currency_name(server))[0]}",
        )
        em.add_field(name="Info:", value=userinfo["info"] or None)
        em.add_field(
            name="Badges:",
            value=(", ".join(userinfo["badges"]).replace("_", " ") or None),
        )
        em.set_author(name="Profile for {}".format(user.name), url=user.display_avatar)
        em.set_thumbnail(url=user.display_avatar)
        return em

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command()
    @commands.guild_only()
    async def rank(self, ctx, *, user: discord.Member = None):
        """Displays the rank of a user."""
        if user is None:
            user = ctx.message.author
        if user.bot:
            ctx.command.reset_cooldown(ctx)
            await ctx.send_help()
            return
        channel = ctx.message.channel
        server = user.guild

        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        # no cooldown for text only
        if await self.config.guild(server).text_only():
            em = await self.rank_text(user, server, userinfo)
            await channel.send(embed=em)
        else:
            async with channel.typing():
                rank = await self.draw_rank(user, server)
                file = discord.File(rank, filename="rank.png")
                await channel.send(
                    "Ranking & Statistics for {}".format(user.mention),
                    file=file,
                    allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
                )
            rank.close()

    async def rank_text(self, user, server, userinfo):
        em = discord.Embed(colour=user.colour)
        em.add_field(
            name="Server Rank",
            value="#{}".format(await self._find_server_rank(user, server)),
        )
        em.add_field(name="Reps", value=userinfo["rep"])
        em.add_field(name="Server Level", value=userinfo["servers"][str(server.id)]["level"])
        em.add_field(name="Server Exp", value=await self._find_server_exp(user, server))
        em.set_author(name="Rank & Statistics for {}".format(user.name), url=user.display_avatar)
        em.set_thumbnail(url=user.display_avatar)
        return em

    @commands.command()
    @commands.guild_only()
    async def lvlinfo(self, ctx, *, user: discord.Member = None):
        """Gives more specific details about user profile image."""
        if not user:
            user = ctx.author
        if user.bot:
            await ctx.send_help()
            return
        server = ctx.guild
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        # creates user if doesn't exist
        await self._create_user(user, server)
        total_server_exp = 0
        for i in range(userinfo["servers"][str(server.id)]["level"]):
            total_server_exp += await self._required_exp(i)
        total_server_exp += userinfo["servers"][str(server.id)]["current_exp"]
        data = {
            "Name": user.name,
            "Title": userinfo["title"],
            "Reps": userinfo["rep"],
            "Server level": userinfo["servers"][str(server.id)]["level"],
            "Server XP": total_server_exp,
            "Total XP": userinfo["total_exp"],
            "Shared servers data": len(userinfo["servers"]),
            "Info": userinfo["info"],
            "Profile background": userinfo["profile_background"],
            "Rank background": userinfo["rank_background"],
            "Levelup background": userinfo["levelup_background"],
            "Badges": "\n".join(userinfo["badges"]),
        }
        for k, v in userinfo.items():
            if ("color" in k) and v:
                data[k.capitalize().replace("_", " ")] = discord.Color.from_rgb(*v[:3])

        em = discord.Embed(description=chat.box(tabulate(data.items())), colour=user.colour)
        em.set_author(
            name="Profile Information for {}".format(user.name),
            icon_url=user.display_avatar,
        )
        await ctx.send(embed=em)
