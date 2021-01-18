import discord
from redbot.core.utils import chat_formatting as chat
from redbot.vendored.discord.ext import menus


class BackgroundMenu(menus.MenuPages, inherit_buttons=False):
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

    @menus.button("\N{RECEIPT}", position=menus.First(0))
    async def switch_profile(self, payload):
        await self.change_source(self.sources["profile"])

    @menus.button("\N{CARD INDEX}", position=menus.First(1))
    async def switch_rank(self, payload):
        await self.change_source(self.sources["rank"])

    @menus.button("\N{SQUARED UP WITH EXCLAMATION MARK}", position=menus.First(2))
    async def switch_levelup(self, payload):
        await self.change_source(self.sources["levelup"])

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
        await self.show_checked_page(self.current_page - 1)

    @menus.button("\N{BLACK RIGHT-POINTING TRIANGLE}\ufe0f", position=menus.Last(0))
    async def go_to_next_page(self, payload):
        """go to the next page"""
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

    async def format_page(self, menu: BackgroundMenu, page):
        name, url = page
        em = discord.Embed(
            title=name,
            color=await menu.ctx.embed_color(),
            url=url,
            description=f"{menu.bg_type.capitalize()} background {menu.current_page+1}/{self.get_max_pages()}",
        )
        em.set_footer(
            text="Legend:\n"
            "\N{RECEIPT} - Profile\n"
            "\N{CARD INDEX} - Rank\n"
            "\N{SQUARED UP WITH EXCLAMATION MARK} - Levelup"
        )
        em.set_image(url=url)
        return em
