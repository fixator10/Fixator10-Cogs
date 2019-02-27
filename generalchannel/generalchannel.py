import discord
from redbot.core import checks
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.mod import get_audit_reason


async def server_set(ctx):
    """Check if member has required role and channel is configured"""
    channel = await ctx.cog.config.guild(ctx.guild).channel()
    if not ctx.guild.get_channel(channel):
        return False


class GeneralChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0x8a87069db515498281c88d41675bf85b)
        default_guild = {
            "channel": None
        }
        self.config.register_guild(**default_guild)

    @commands.group(invoke_without_command=True, name="generalchannel")
    @commands.guild_only()
    async def gc(self, ctx):
        """Change general server's channel name/topic"""
        pass

    @gc.group()
    @checks.admin_or_permissions(manage_channels=True)
    async def set(self, ctx):
        """Set general channel and roles for it"""
        pass

    @set.command(name="channel")
    async def setchannel(self, ctx, channel: discord.TextChannel = None):
        """Set #general channel

        Clears setting if channel not specified"""
        if channel:
            await self.config.guild(ctx.guild).channel.set(channel.id)
        else:
            await self.config.guild(ctx.guild).channel.clear()
        await ctx.tick()

    @gc.command(name="name")
    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.check(server_set)
    async def gcname(self, ctx, *, name: str):
        """Change name of #general"""
        channel = await self.config.guild(ctx.guild).channel()
        channel = ctx.guild.get_channel(channel)
        if len(name) > 100:
            name = name[:100]
        try:
            await channel.edit(name=name, reason=get_audit_reason(ctx.author, "General channel name change"))
        except discord.Forbidden:
            await ctx.send(chat.error("Unable to change channel's name: Missing permissions"))
        except discord.HTTPException:
            await ctx.send(chat.error("Unable to change channel's name: Failed."))
        else:
            await ctx.tick()

    @gc.command(name="topic")
    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.check(server_set)
    async def gctopic(self, ctx, *, topic: str = None):
        """Change topic of #general

        Use `[p]generalchannel topic +<text>` to add text
        to end of topic"""
        channel = await self.config.guild(ctx.guild).channel()
        channel = ctx.guild.get_channel(channel)
        if topic is not None:
            if len(topic) > 1024:
                topic = topic[:1024]
            if topic.startswith("+"):
                topic = topic[1:].strip()
                topic = "{}\n{}".format((channel.topic or ""), topic)
                if len(topic) > 1024:
                    topic = topic[-1024:]
        try:
            await channel.edit(topic=topic, reason=get_audit_reason(ctx.author, "General channel name change"))
        except discord.Forbidden:
            await ctx.send(chat.error("Unable to change channel's topic: Missing permissions"))
        except discord.HTTPException:
            await ctx.send(chat.error("Unable to change channel's topic: Failed."))
        else:
            await ctx.tick()
