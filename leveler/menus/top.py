import asyncio
from contextlib import suppress

import discord
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.predicates import MessagePredicate
from redbot.vendored.discord.ext import menus
from tabulate import tabulate


class TopMenu(menus.MenuPages, inherit_buttons=False):
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

    @menus.button("\N{NUMBER SIGN}\ufe0f\N{COMBINING ENCLOSING KEYCAP}", position=menus.Last(2))
    async def number_page(self, payload):
        prompt = await self.ctx.send("Send a number of page that you wish to see")
        try:
            pred = MessagePredicate.positive(self.ctx)
            msg = await self.bot.wait_for(
                "message_without_command",
                check=pred,
                timeout=10.0,
            )
            if pred.result:
                jump_page = int(msg.content)
                if jump_page > self._source.get_max_pages():
                    jump_page = self._source.get_max_pages()
                await self.show_checked_page(jump_page - 1)
                if self.ctx.channel.permissions_for(self.ctx.me).manage_messages:
                    with suppress(discord.HTTPException):
                        await msg.delete()
        except asyncio.TimeoutError:
            pass
        finally:
            with suppress(discord.HTTPException):
                await prompt.delete()

    @menus.button("\N{CROSS MARK}", position=menus.First(2))
    async def stop_pages(self, payload: discord.RawReactionActionEvent) -> None:
        self.stop()


class TopPager(menus.ListPageSource):
    def __init__(
        self, entries, board_type: str, is_level: bool, user_stats: list, icon_url: str, title: str
    ):
        super().__init__(entries, per_page=15)
        self.board_type = board_type
        self.is_level = is_level
        self.user = user_stats
        self.icon_url = icon_url
        self.title = title

    async def format_page(self, menu: TopMenu, entries):
        table = tabulate(
            entries,
            headers=["#", self.board_type, "Level", "Username"]
            if self.is_level
            else ["#", self.board_type, "Username"],
            tablefmt="rst",
        )
        table_width = len(table.splitlines()[0])
        msg = ""
        msg += "[Page {}/{}]".format(menu.current_page + 1, self.get_max_pages()).rjust(
            table_width
        )
        msg += "\n"
        msg += table
        msg += "\n"
        if self.user:
            msg += "Your rank: {}".format(self.user[0]).rjust(table_width)
            msg += "\n"
            msg += "{}: {}".format(self.board_type, self.user[1]).rjust(table_width)
            msg += "\n"
        embed = discord.Embed(color=await menu.ctx.embed_color(), description=chat.box(msg))
        embed.set_author(name=self.title, icon_url=self.icon_url)
        return embed
