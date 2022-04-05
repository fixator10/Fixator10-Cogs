import asyncio
import contextlib
from datetime import datetime
from typing import Any, Dict

import aiohttp
import discord
from redbot.core import __version__ as red_version
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.menus import DEFAULT_CONTROLS, close_menu, menu

from .iso639 import LANGUAGE_MAP

BASE_API_URL = "https://vocadb.net/api/songs"


class VocaDB(commands.Cog):
    """Fetch Vocaloid song lyrics on VocaDB.net database!"""

    __authors__ = ["ow0x", "Fixator10"]
    __version__ = "0.1.2"

    def format_help_for_context(self, ctx: commands.Context) -> str:  # Thanks Sinbad!
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\n**Version:** {self.__version__}"

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self) -> None:
        asyncio.create_task(self.session.close())

    async def red_delete_data_for_user(self, **kwargs) -> None:
        """Nothing to delete"""
        pass

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse a date string from VocaDB API"""
        datetime_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        return f"<t:{int(datetime_obj.timestamp())}:d>"

    async def _fetch_data(self, ctx: commands.Context, query: str):
        """Fetch data from VocaDB API and prompt the user to select an entry"""
        params = {
            "query": query,
            "maxResults": 10,
            "sort": "FavoritedTimes",
            "preferAccurateMatches": "true",
            "nameMatchMode": "Words",
            "fields": "Artists,Lyrics,Names,ThumbUrl",
        }
        headers = {
            "User-Agent": f"Red-DiscordBot/{red_version} Fixator10-cogs/VocaDB/{self.__version__}"
        }
        try:
            async with self.session.get(BASE_API_URL, params=params, headers=headers) as resp:
                if resp.status != 200:
                    return f"https://http.cat/{resp.status}"
                result = await resp.json()
        except asyncio.TimeoutError:
            return "Request timed out"

        all_items = result.get("items")
        if not all_items:
            return None

        filtered_items = [x for x in all_items if x.get("lyrics")]
        if not filtered_items:
            return None

        if len(filtered_items) == 1:
            return filtered_items[0]

        items = "\n".join(
            f"**`[{i}]`** {x.get('defaultName')} - {x.get('artistString')}"
            f" (published: {self._parse_date(x.get('publishDate'))})"
            for i, x in enumerate(filtered_items, start=1)
        )

        prompt = await ctx.send(
            f"Found below **{len(filtered_items)}** result(s). Pick one in 60 seconds:\n\n{items}"
        )

        def check(msg: discord.Message) -> bool:
            return bool(
                msg.content.isdigit()
                and int(msg.content) in range(len(filtered_items) + 1)
                and msg.author.id == ctx.author.id
                and msg.channel.id == ctx.channel.id
            )

        try:
            choice = await self.bot.wait_for("message", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            choice = None

        if choice is None or choice.content.strip() == "0":
            with contextlib.suppress(discord.NotFound, discord.HTTPException):
                await prompt.edit(content="Cancelled.", delete_after=5.0)
            return None

        choice = int(choice.content.strip()) - 1
        with contextlib.suppress(discord.NotFound, discord.HTTPException):
            await prompt.delete()
        return filtered_items[choice]

    def _info_embed(self, colour, data: Dict[str, Any]) -> discord.Embed:
        """Create an embed with the song info"""
        minutes = data.get("lengthSeconds", 0) // 60
        seconds = data.get("lengthSeconds", 0) % 60
        pub_date = self._parse_date(data.get("publishDate"))
        all_artists = ", ".join(
            f"[{x.get('name')}](https://vocadb.net/Ar/{x.get('id')}) ({x.get('categories')})"
            for x in data.get("artists")
        )
        embed = discord.Embed(colour=colour)
        embed.title = f"{data.get('defaultName')} - {data.get('artistString')}"
        embed.url = f"https://vocadb.net/S/{data.get('id')}"
        embed.set_thumbnail(url=data.get("thumbUrl", ""))
        embed.add_field(name="Duration", value=f"{minutes} minutes, {seconds} seconds")
        favorites, score = (data.get("favoritedTimes", 0), data.get("ratingScore", 0))
        embed.add_field(name="Published On", value=pub_date)
        embed.add_field(name="Statistics", value=f"{favorites} favourite(s), {score} total score")
        embed.add_field(name="Artist(s)", value=all_artists)
        embed.set_footer(text="Powered by VocaDB")
        return embed

    @staticmethod
    def _lyrics_embed(colour, page: Dict[str, Any], data: Dict[str, Any]) -> discord.Embed:
        """Create an embed with the lyrics"""
        title = [
            x.get("value")
            for x in data.get("names")
            if x.get("language") == LANGUAGE_MAP.get(page["cultureCode"])
        ]
        em = discord.Embed(
            title=title[0] if title else data.get("defaultName"),
            colour=colour,
        )
        em.set_thumbnail(url=data.get("thumbUrl") or "")
        if data.get("id"):
            em.url = f"https://vocadb.net/S/{data['id']}"
        em.description = page["value"][:4090] if page.get("value") else "No lyrics found."
        if page.get("url"):
            em.add_field(
                name="Source",
                value=f"[{page.get('source') or 'Source'}]({page['url']})",
            )
        return em

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def vocadb(self, ctx: commands.Context, *, query: str):
        """Fetch Vocaloid song lyrics from VocaDB.net database"""
        await ctx.trigger_typing()
        data = await self._fetch_data(ctx, query)

        if type(data) == str:
            return await ctx.send(data)
        if not data:
            return await ctx.send("No results found.")

        await ctx.send(embed=self._info_embed(await ctx.embed_colour(), data))
        # Added a small delay to improve UX for initial embed
        await asyncio.sleep(2.0)

        embeds = []
        for i, page in enumerate(data["lyrics"], start=1):
            language = f"Language: {LANGUAGE_MAP.get(page.get('cultureCode', 'na'))}"
            emb = self._lyrics_embed(await ctx.embed_colour(), page, data)
            emb.set_footer(text=f"{language} • Page {i} of {len(data['lyrics'])}")
            embeds.append(emb)

        controls = {"\N{CROSS MARK}": close_menu} if len(embeds) == 1 else DEFAULT_CONTROLS
        await menu(ctx, embeds, controls=controls, timeout=90.0)
