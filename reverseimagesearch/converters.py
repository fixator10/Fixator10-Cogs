# https://github.com/TrustyJAID/Trusty-cogs/blob/master/notsobot/converter.py

import re

from discord.ext.commands.converter import Converter
from discord.ext.commands.errors import BadArgument
from redbot.core.i18n import Translator

_ = Translator("ReverseImageSearch", __file__)

IMAGE_LINKS = re.compile(
    r"(https?://[^\"\'\s]*\.(?:png|jpg|jpeg|gif|svg)(\?size=[0-9]*)?)", flags=re.I
)
EMOJI_REGEX = re.compile(r"(<(a)?:[a-zA-Z0-9_]+:([0-9]+)>)")
MENTION_REGEX = re.compile(r"<@!?([0-9]+)>")
ID_REGEX = re.compile(r"[0-9]{17,}")


class ImageFinder(Converter):
    """
    This is a class to convert notsobots image searching capabilities
    into a more general converter class
    """

    async def convert(self, ctx, argument):
        attachments = ctx.message.attachments
        mentions = MENTION_REGEX.finditer(argument)
        matches = IMAGE_LINKS.finditer(argument)
        emojis = EMOJI_REGEX.finditer(argument)
        ids = ID_REGEX.finditer(argument)
        urls = []
        if matches:
            for match in matches:
                # print(match.group(1))
                urls.append(match.group(1))
        if emojis:
            for emoji in emojis:
                ext = "gif" if emoji.group(2) else "png"
                url = "https://cdn.discordapp.com/emojis/{id}.{ext}?v=1".format(
                    id=emoji.group(3), ext=ext
                )
                urls.append(url)
        if mentions:
            for mention in mentions:
                user = ctx.guild.get_member(int(mention.group(1)))
                if user.is_avatar_animated():
                    url = IMAGE_LINKS.search(str(user.avatar_url_as(format="gif")))
                else:
                    url = IMAGE_LINKS.search(str(user.avatar_url_as(format="png")))
                urls.append(url.group(1))
        if not urls and ids:
            for possible_id in ids:
                user = ctx.guild.get_member(int(possible_id.group(0)))
                if user:
                    if user.is_avatar_animated():
                        url = IMAGE_LINKS.search(str(user.avatar_url_as(format="gif")))
                    else:
                        url = IMAGE_LINKS.search(str(user.avatar_url_as(format="png")))
                    urls.append(url.group(1))
        if attachments:
            for attachment in attachments:
                urls.append(attachment.url)

        if not urls:
            ctx.command.reset_cooldown(ctx)
            raise BadArgument(_("No images provided."))
        return urls

    async def search_for_images(self, ctx):
        urls = []
        async for message in ctx.channel.history(limit=10):
            if message.attachments:
                for attachment in message.attachments:
                    urls.append(attachment.url)
            match = IMAGE_LINKS.match(message.content)
            if match:
                urls.append(match.group(1))
        if not urls:
            ctx.command.reset_cooldown(ctx)
            raise ValueError(_("No Images found in recent history."))
        return urls
