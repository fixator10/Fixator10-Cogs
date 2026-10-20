from typing import Dict

import discord
from redbot.vendored.discord.ext import menus

from .base import BaseView


class ChangeSourceButton(discord.ui.Button):
    def __init__(self, label: str, source: menus.PageSource):
        super().__init__(style=discord.ButtonStyle.grey, label=label)
        self.source = source

    async def callback(self, interaction: discord.Interaction):
        kwargs = await self.view.change_source(self.source)
        await interaction.response.edit_message(**kwargs)


class BackgroundMenu(BaseView):
    def __init__(self, sources: Dict[str, menus.PageSource], style: str):
        self.sources = sources
        self.bg_type = style
        super().__init__(source=self.sources[style])
        for key, value in self.sources.items():
            nb = ChangeSourceButton(key, value)
            self.add_item(nb)


class BackgroundMenu_old(menus.MenuPages, inherit_buttons=False):
    def __init__(
        self,
        sources: dict,
        bg_type: str,
        timeout: int = 30,
    ):
        super().__init__(
            sources[bg_type],
            timeout=timeout,
            clear_reactions_after=True,
            delete_message_after=True,
        )
        self.sources = sources
        self.bg_type = bg_type

    async def finalize(self, timed_out):
        """|coro|
        A coroutine that is called when the menu loop has completed
        its run. This is useful if some asynchronous clean-up is
        required after the fact.
        Parameters
        --------------
        timed_out: :class:`bool`
            Whether the menu completed due to timing out.
        """
        if timed_out and self.delete_message_after:
            self.delete_message_after = False

    def should_add_reactions(self):
        return True

    async def set_source(self, bg_type):
        self.bg_type = bg_type
        await self.change_source(self.sources[bg_type])

    @menus.button("\N{RECEIPT}", position=menus.First(0))
    async def switch_profile(self, payload):
        await self.set_source("profile")

    @menus.button("\N{CARD INDEX}", position=menus.First(1))
    async def switch_rank(self, payload):
        await self.set_source("rank")

    @menus.button("\N{SQUARED UP WITH EXCLAMATION MARK}", position=menus.First(2))
    async def switch_levelup(self, payload):
        await self.set_source("levelup")

    @menus.button(
        "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        position=menus.First(3),
    )
    async def go_to_first_page(self, payload):
        """go to the first page"""
        await self.show_page(0)

    @menus.button("\N{BLACK LEFT-POINTING TRIANGLE}\ufe0f", position=menus.First(4))
    async def go_to_previous_page(self, payload):
        """go to the previous page"""
        if self.current_page == 0:
            await self.show_page(self._source.get_max_pages() - 1)
        else:
            await self.show_checked_page(self.current_page - 1)

    @menus.button("\N{BLACK RIGHT-POINTING TRIANGLE}\ufe0f", position=menus.Last(0))
    async def go_to_next_page(self, payload):
        """go to the next page"""
        if self.current_page == self._source.get_max_pages() - 1:
            await self.show_page(0)
        else:
            await self.show_checked_page(self.current_page + 1)

    @menus.button(
        "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        position=menus.Last(1),
    )
    async def go_to_last_page(self, payload):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(self._source.get_max_pages() - 1)

    @menus.button("\N{CROSS MARK}", position=menus.First(5))
    async def stop_pages(self, payload: discord.RawReactionActionEvent) -> None:
        self.stop()


class BackgroundPager(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries, per_page=1)
        self.select_options = [
            discord.SelectOption(label=x[0], description=f"Page {num+1}", value=str(num))
            for num, x in enumerate(entries)
        ]

    async def format_page(self, menu: BackgroundMenu, page):
        name, url = page
        em = discord.Embed(
            title=name,
            color=await menu.ctx.embed_color(),
            url=url,
            description=f"{menu.bg_type.capitalize()} background {menu.current_page+1}/{self.get_max_pages()}",
        )
        em.set_footer(
            text="Legend: \N{RECEIPT} - Profile | "
            "\N{CARD INDEX} - Rank | "
            "\N{SQUARED UP WITH EXCLAMATION MARK} - Levelup"
        )
        em.set_image(url=url)
        return em
