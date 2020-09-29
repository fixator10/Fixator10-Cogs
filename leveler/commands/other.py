import time

import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from ..abc import CompositeMetaClass, MixinMeta


class Other(MixinMeta, metaclass=CompositeMetaClass):
    """Other commands"""

    @commands.command()
    @commands.guild_only()
    async def rep(self, ctx, *, user: discord.Member = None):
        """Gives a reputation point to a designated player."""
        org_user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        if user:
            await self._create_user(user, server)
        org_userinfo = await self.db.users.find_one({"user_id": str(org_user.id)})
        curr_time = time.time()

        if user and user.id == org_user.id:
            await ctx.send("**You can't give a rep to yourself!**")
            return
        if user and user.bot:
            await ctx.send("**You can't give a rep to a bot!**")
            return
        if user and await self.config.rep_rotation() and user.id == org_userinfo.get("lastrep"):
            await ctx.send("**You already gave a rep point to this user!**")
            return
        if "rep_block" not in org_userinfo:
            org_userinfo["rep_block"] = 0

        delta = float(curr_time) - float(org_userinfo["rep_block"])
        if user and delta >= 43200.0 and delta > 0:
            userinfo = await self.db.users.find_one({"user_id": str(user.id)})
            await self.db.users.update_one(
                {"user_id": str(org_user.id)}, {"$set": {"lastrep": user.id}}
            )
            await self.db.users.update_one(
                {"user_id": str(org_user.id)}, {"$set": {"rep_block": curr_time}}
            )
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"rep": userinfo["rep"] + 1}}
            )
            await ctx.send(
                "**You have just given {} a reputation point!**".format(user.mention),
                allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
            )
        else:
            # calulate time left
            seconds = 43200 - delta
            if seconds < 0:
                await ctx.send("**You can give a rep!**")
                return
            await ctx.send(
                "**You need to wait {} until you can give reputation again!**".format(
                    chat.humanize_timedelta(seconds=seconds)
                )
            )

    @commands.command(name="backgrounds", usage="<type>")
    @commands.guild_only()
    async def disp_backgrounds(self, ctx, bg_type: str):
        """Gives a list of backgrounds.

        type can be: `profile`, `rank` or `levelup`."""
        server = ctx.guild
        backgrounds = await self.config.backgrounds()

        em = discord.Embed(colour=await ctx.embed_color())
        if bg_type.lower() == "profile":
            em.set_author(
                name="Profile Backgrounds for {}".format(self.bot.user.name),
                icon_url=self.bot.user.avatar_url,
            )
            bg_key = "profile"
        elif bg_type.lower() == "rank":
            em.set_author(
                name="Rank Backgrounds for {}".format(self.bot.user.name),
                icon_url=self.bot.user.avatar_url,
            )
            bg_key = "rank"
        elif bg_type.lower() == "levelup":
            em.set_author(
                name="Level Up Backgrounds for {}".format(self.bot.user.name),
                icon_url=self.bot.user.avatar_url,
            )
            bg_key = "levelup"
        else:
            bg_key = None

        if bg_key:
            embeds = []
            total = len(backgrounds[bg_key])
            cnt = 1
            for bg in sorted(backgrounds[bg_key].keys()):
                em = discord.Embed(
                    title=bg,
                    color=await ctx.embed_color(),
                    url=backgrounds[bg_key][bg],
                    description=f"Background {cnt}/{total}",
                )
                em.set_image(url=backgrounds[bg_key][bg])
                embeds.append(em)
                cnt += 1
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send("**Invalid background type. Must be `profile`, `rank` or `levelup`.**")
