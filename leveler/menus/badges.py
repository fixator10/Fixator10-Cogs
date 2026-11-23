import discord
from redbot.core import commands
from redbot.core.bank import get_currency_name
from redbot.vendored.discord.ext import menus

from .base import BaseView


class BuyBadgeButton(discord.ui.Button):
    def __init__(
        self,
        label: str,
        emoji: str,
    ):
        super().__init__(style=discord.ButtonStyle.grey, label=label, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        page = await self.view.source.get_page(self.view.current_page)
        await self.view.ctx.invoke(
            self.view.ctx.cog.buy_badge,
            is_global=True if page["server_id"] == "global" else False,
            name=page["badge_name"],
        )


class BadgeMenu(BaseView):
    def __init__(self, source: menus.PageSource, timeout: int = 180, can_buy: bool = False):
        super().__init__(source, timeout=timeout)
        self.can_buy = can_buy
        self.buy_button = BuyBadgeButton(label="Buy", emoji="\N{BANKNOTE WITH DOLLAR SIGN}")
        self.add_item(self.buy_button)

    async def start(self, ctx: commands.Context):
        if self.can_buy:
            self.can_buy = await ctx.cog.buy_badge.can_run(ctx, check_all_parents=True)
        await super().start(ctx)


class BadgeMenu_old(menus.MenuPages, inherit_buttons=False):
    def __init__(
        self,
        source: menus.PageSource,
        timeout: int = 30,
        can_buy=False,
    ):
        super().__init__(
            source,
            timeout=timeout,
            clear_reactions_after=True,
            delete_message_after=True,
        )
        self.can_buy = can_buy

    async def start(self, ctx, *, channel=None, wait=False):
        if self.can_buy:
            self.can_buy = await ctx.cog.buy_badge.can_run(ctx, check_all_parents=True)
        await super().start(ctx, channel=channel, wait=wait)

    def should_add_reactions(self):
        return True

    def _no_pages(self):
        return not self._source.is_paginating()

    def _skip_double_triangle_buttons(self):
        return (not self._source.is_paginating()) or super()._skip_double_triangle_buttons()

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

    def cant_buy_check(self):
        return not self.can_buy

    @menus.button("\N{BANKNOTE WITH DOLLAR SIGN}", position=menus.First(0), skip_if=cant_buy_check)
    async def buy_badge(self, payload):
        page = await self.source.get_page(self.current_page)
        await self.ctx.invoke(
            self.ctx.cog.buy_badge,
            is_global=True if page["server_id"] == "global" else False,
            name=page["badge_name"],
        )

    @menus.button(
        "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
        position=menus.First(0),
        skip_if=_skip_double_triangle_buttons,
    )
    async def go_to_first_page(self, payload):
        """go to the first page"""
        await self.show_page(0)

    @menus.button(
        "\N{BLACK LEFT-POINTING TRIANGLE}\ufe0f", position=menus.First(1), skip_if=_no_pages
    )
    async def go_to_previous_page(self, payload):
        """go to the previous page"""
        if self.current_page == 0:
            await self.show_page(self._source.get_max_pages() - 1)
        else:
            await self.show_checked_page(self.current_page - 1)

    @menus.button(
        "\N{BLACK RIGHT-POINTING TRIANGLE}\ufe0f", position=menus.Last(0), skip_if=_no_pages
    )
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


class AvailableBadgePager(menus.ListPageSource):
    def __init__(self, entries, server_name, server_id, icon):
        super().__init__(entries, per_page=1)
        self.server_name = server_name
        self.icon = icon
        self.server_id = server_id
        self.select_options = [
            discord.SelectOption(
                label=x.get("badge_name", "No Name Badge"),
                description=f"Page {num+1}",
                value=str(num),
            )
            for num, x in enumerate(entries)
        ]

    async def format_page(self, menu: BadgeMenu, page):
        em = discord.Embed(
            title=page["badge_name"],
            description=page["description"],
            color=int(page["border_color"][1:], base=16),
        )
        if page["price"] > 0:
            em.add_field(
                name="Price", value=f"{page['price']}{await get_currency_name(menu.ctx.guild)}"
            )
        elif page["price"] == 0:
            em.add_field(name="Price", value="Free")
        em.set_author(name=self.server_name, icon_url=self.icon)
        em.set_thumbnail(url=page["bg_img"])
        em.set_footer(text=f"Badge {menu.current_page+1}/{self.get_max_pages()}")
        return em


class OwnBadgePager(menus.ListPageSource):
    def __init__(self, entries, user: discord.Member):
        super().__init__(entries, per_page=1)
        self.user = user
        self.select_options = [
            discord.SelectOption(
                label=x.get("badge_name", "No Name Badge"),
                description=f"Page {num+1}",
                value=str(num),
            )
            for num, x in enumerate(entries)
        ]

    async def format_page(self, menu: BadgeMenu, page):
        em = discord.Embed(
            title=page["badge_name"],
            description=page["description"],
            color=int(page["border_color"][1:], base=16),
        )
        em.set_author(name=self.user.display_name, icon_url=self.user.display_avatar)
        em.set_thumbnail(url=page["bg_img"])
        em.set_footer(
            text=f"Server: {page['server_name']} • Badge {menu.current_page+1}/{self.get_max_pages()}"
        )
        return em
