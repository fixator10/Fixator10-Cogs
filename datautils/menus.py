import discord
from redbot.core.utils import chat_formatting as chat
from redbot.vendored.discord.ext import menus

from .common_variables import KNOWN_CHANNEL_TYPES
from .embeds import activity_embed, emoji_embed
from .utils import _


def check_channels(channel_type: str):
    def predicate(self):
        return channel_type not in self.sources

    return predicate


class BaseMenu(menus.MenuPages, inherit_buttons=False):
    def __init__(
        self,
        source: menus.PageSource,
        timeout: int = 30,
    ):
        super().__init__(
            source,
            timeout=timeout,
            clear_reactions_after=True,
            delete_message_after=True,
        )

    def _skip_double_triangle_buttons(self):
        return super()._skip_double_triangle_buttons()

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

    @menus.button(
        "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        position=menus.First(0),
        skip_if=_skip_double_triangle_buttons,
    )
    async def go_to_first_page(self, payload):
        """go to the first page"""
        await self.show_page(0)

    @menus.button("\N{BLACK LEFT-POINTING TRIANGLE}\ufe0f", position=menus.First(1))
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
        skip_if=_skip_double_triangle_buttons,
    )
    async def go_to_last_page(self, payload):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(self._source.get_max_pages() - 1)

    @menus.button("\N{CROSS MARK}", position=menus.First(2))
    async def stop_pages(self, payload: discord.RawReactionActionEvent) -> None:
        self.stop()


class ChannelsMenu(menus.MenuPages, inherit_buttons=False):
    def __init__(self, sources: dict, channel_type: str, total_channels: int, timeout: int = 30):
        super().__init__(
            sources[next(iter(sources))],
            timeout=timeout,
            clear_reactions_after=True,
            delete_message_after=True,
        )
        self.sources = sources
        self.channel_type = channel_type
        self.total_channels = total_channels

    async def set_source(self, channel_type):
        self.channel_type = channel_type
        await self.change_source(self.sources[channel_type])

    def should_add_reactions(self):
        return True

    @menus.button("\N{BOOKMARK TABS}", position=menus.First(0), skip_if=check_channels("category"))
    async def switch_category(self, payload):
        await self.set_source("category")

    @menus.button("\N{SPEECH BALLOON}", position=menus.First(1), skip_if=check_channels("text"))
    async def switch_text(self, payload):
        await self.set_source("text")

    @menus.button("\N{SPEAKER}", position=menus.First(2), skip_if=check_channels("voice"))
    async def switch_voice(self, payload):
        await self.set_source("voice")

    @menus.button(
        "\N{SATELLITE ANTENNA}",
        position=menus.First(3),
        skip_if=check_channels("stage"),
    )
    async def switch_stage(self, payload):
        await self.set_source("stage")

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


class ChannelsPager(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries, per_page=19)
        # 100 chars per channel name = 20 channels per page, minus line breaks

    async def format_page(self, menu: ChannelsMenu, entries):
        e = discord.Embed(
            title="{}:".format(_(KNOWN_CHANNEL_TYPES[menu.channel_type][1])),
            description=chat.box("\n".join(c.name for c in entries))
            if entries
            else _("No channels"),
        )
        e.set_footer(
            text=_("Page {}/{} • {}: {} • Total channels: {}").format(
                menu.current_page + 1,
                self.get_max_pages() or 1,
                _(KNOWN_CHANNEL_TYPES[menu.channel_type][1]),
                len(self.entries),
                menu.total_channels,
            )
        )
        return e


class PagePager(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu: BaseMenu, page):
        return chat.box(page)


class EmojiPager(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu: BaseMenu, page):
        e = await emoji_embed(menu.ctx, page)
        e.set_footer(text=_("Page {}/{}").format(menu.current_page + 1, self.get_max_pages()))
        return e


class ActivityPager(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu: BaseMenu, page):
        return await activity_embed(menu.ctx, page)
