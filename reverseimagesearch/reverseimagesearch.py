from contextlib import suppress
from io import BytesIO

import aiohttp
import discord
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from .converters import ImageFinder
from .saucenao import SauceNAO
from .tracemoe import TraceMoe

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json

_ = Translator("ReverseImageSearch", __file__)


async def send_preview(
    ctx: commands.Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
):
    with suppress(discord.NotFound):
        await message.delete()
    doc = ctx.search_docs[page]
    async with ctx.typing():
        try:
            async with ctx.cog.session.get(
                doc.preview_scene, raise_for_status=True
            ) as video_preview:
                video_preview = BytesIO(await video_preview.read())
                await ctx.send(
                    embed=pages[page],
                    file=discord.File(video_preview, filename=doc.filename),
                )
                video_preview.close()
        except aiohttp.ClientResponseError as e:
            await ctx.send(_("Unable to get video preview: {}").format(e.message))
        except discord.HTTPException as e:
            await ctx.send(_("Unable to send video preview: {}").format(e))


TRACEMOE_MENU_CONTROLS = {**DEFAULT_CONTROLS, "\N{FILM FRAMES}": send_preview}


@cog_i18n(_)
class ReverseImageSearch(commands.Cog):
    """(Anime) Reverse Image Search"""

    __version__ = "2.1.4"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.saucenao_limits = {
            "short": None,
            "long": None,
            "long_remaining": None,
            "short_remaining": None,
        }
        self.session = aiohttp.ClientSession(json_serialize=json.dumps)
        self.config = Config.get_conf(self, identifier=0x02E801D017C140A9A0C840BA01A25066)
        default_global = {"numres": 6}
        self.config.register_global(**default_global)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def red_delete_data_for_user(self, **kwargs):
        return

    @commands.group(invoke_without_command=True)
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def saucenao(self, ctx, image: ImageFinder = None):
        """Reverse search image via SauceNAO"""
        if image is None:
            try:
                image = await ImageFinder().search_for_images(ctx)
            except ValueError as e:
                await ctx.send(e)
                return
        image = image[0]
        try:
            search = await SauceNAO.from_image(ctx, image)
        except ValueError as e:
            await ctx.send(e)
            return
        if not search.results:
            await ctx.send(_("Nothing found"))
            return
        self.saucenao_limits["short"] = search.limits.short
        self.saucenao_limits["long"] = search.limits.long
        self.saucenao_limits["long_remaining"] = search.limits.remaining.long
        self.saucenao_limits["short_remaining"] = search.limits.remaining.short
        embeds = []
        page = 0
        for entry in search.results:
            page += 1
            try:
                url = entry.urls[0]
            except IndexError:
                url = None
            # design is shit, ideas?
            e = discord.Embed(
                title=entry.source or entry.title or entry.service,
                description="\n".join(
                    [
                        _("Similarity: {}%").format(entry.similarity),
                        "\n".join([n for n in [entry.eng_name, entry.jp_name] if n]) or "",
                        entry.part and _("Part/Episode: {}").format(entry.part) or "",
                        entry.year and _("Year: {}").format(entry.year) or "",
                        entry.est_time and _("Est. Time: {}").format(entry.est_time) or "",
                    ]
                ),
                url=url,
                color=await ctx.embed_colour(),
                timestamp=entry.created_at or discord.Embed.Empty,
            )
            e.set_footer(
                text=_("Via SauceNAO • Page {}/{}").format(page, search.results_returned),
                icon_url="https://www.google.com/s2/favicons?domain=saucenao.com",
            )
            e.set_thumbnail(url=entry.thumbnail)
            embeds.append(e)
        if embeds:
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send(chat.info(_("Nothing found")))

    @saucenao.command()
    @commands.is_owner()
    async def apikey(self, ctx):
        """Set API key for SauceNAO"""
        message = _(
            "To get SauceNAO API key:\n"
            "1. [Login](https://saucenao.com/user.php) to your SauceNAO account\n"
            "2. Go to [Search > api](https://saucenao.com/user.php?page=search-api) page\n"
            "3. Copy your *api key*\n"
            "4. Use `{}set api reverseimagesearch saucenao <your_api_key>`\n\n"
            "Note: These tokens are sensitive and should only be used in a private channel\n"
            "or in DM with the bot."
        ).format(ctx.clean_prefix)
        await ctx.maybe_send_embed(message)

    @saucenao.command(alises=["numres"])
    @commands.is_owner()
    async def maxres(self, ctx, results: int = 6):
        """Set API count of results count for SauceNAO

        6 by default"""
        await self.config.numres.set(results)
        await ctx.tick()

    @saucenao.command(name="stats")
    @commands.is_owner()
    async def saucenao_stats(self, ctx):
        """See how many requests are left"""
        if any(limit is not None for limit in self.saucenao_limits.values()):
            await ctx.send(
                _(
                    "Remaining requests:\nShort (30 seconds): {}/{}\nLong: (24 hours): {}/{}"
                ).format(
                    self.saucenao_limits["short_remaining"],
                    self.saucenao_limits["short"],
                    self.saucenao_limits["long_remaining"],
                    self.saucenao_limits["long"],
                )
            )
        else:
            await ctx.send(_("Command `{}` has not been used yet").format(self.saucenao))

    @commands.group(invoke_without_command=True, aliases=["WAIT"])
    async def tracemoe(self, ctx, image: ImageFinder = None):
        """Reverse search image via WAIT

        If search performed not in NSFW channel, NSFW results will be not shown"""
        if image is None:
            try:
                image = await ImageFinder().search_for_images(ctx)
            except ValueError as e:
                await ctx.send(e)
                return
        image = image[0]
        try:
            search = await TraceMoe.from_image(ctx, image)
        except ValueError as e:
            await ctx.send(e)
            return
        embeds = []
        page = 0
        for doc in search.docs:
            page += 1
            if ctx.channel.nsfw and doc.is_adult:
                continue
            # this design is kinda shit too, ideas, plssss
            e = discord.Embed(
                title=doc.title,
                description="\n".join(
                    [
                        s
                        for s in [
                            _("Similarity: {:.2f}%").format(doc.similarity * 100),
                            doc.title_native
                            and "🇯🇵 " + _("Native title: {}").format(doc.title_native),
                            doc.title_romaji
                            and "🇯🇵 " + _("Romaji transcription: {}").format(doc.title_romaji),
                            doc.title_chinese
                            and "🇨🇳 " + _("Chinese title: {}").format(doc.title_chinese),
                            doc.title_english
                            and "🇺🇸 " + _("English title: {}").format(doc.title_english),
                            _("Est. Time: {}").format(doc.time_str),
                            _("Episode: {}").format(doc.episode),
                            doc.synonyms
                            and _("Also known as: {}").format(", ".join(doc.synonyms)),
                        ]
                        if s
                    ]
                ),
                url=doc.mal_id
                and f"https://myanimelist.net/anime/{doc.mal_id}"
                or f"https://anilist.co/anime/{doc.anilist_id}",
                color=await ctx.embed_color(),
            )
            e.set_thumbnail(url=doc.thumbnail)
            e.set_footer(
                text=_("Via WAIT (trace.moe) • Page {}/{}").format(page, len(search.docs)),
                icon_url="https://trace.moe/favicon128.png",
            )
            embeds.append(e)
        if embeds:
            ctx.search_docs = search.docs
            await menu(ctx, embeds, TRACEMOE_MENU_CONTROLS)
        else:
            await ctx.send(chat.info(_("Nothing found")))

    @tracemoe.command(name="stats")
    @commands.is_owner()
    async def tracemoe_stats(self, ctx):
        """See how many requests are left and time until reset"""
        stats = await TraceMoe.me(ctx)
        await ctx.send(
            _(
                "Remaining requests (ratelimit): {}/{}\n"
                "Remaining requests (quota): {}/{}\n"
                "Ratelimit reset in {}/{}\n"
                "Quota reset in {}/{}\n"
            ).format(
                stats.limit,
                stats.user_limit,
                stats.quota,
                stats.user_quota,
                stats.limit_ttl,
                stats.user_limit_ttl,
                stats.quota_ttl,
                stats.user_quota_ttl,
            )
        )
