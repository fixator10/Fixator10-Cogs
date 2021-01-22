from asyncio import TimeoutError as AsyncTimeoutError
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial

import discord
from redbot.core import bank
from redbot.core.utils.predicates import MessagePredicate

from .abc import MixinMeta


class Utils(MixinMeta):
    """Utility methods"""

    async def asyncify(self, func, *args, **kwargs):
        """Run func in executor"""
        return await self.bot.loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def asyncify_thread(self, func, *args, **kwargs):
        """Run func in thread executor"""
        with ThreadPoolExecutor() as pool:
            return await self.bot.loop.run_in_executor(pool, partial(func, *args, **kwargs))

    async def asyncify_process(self, func, *args, **kwargs):
        """Run func in process executor"""
        with ProcessPoolExecutor() as pool:
            return await self.bot.loop.run_in_executor(pool, partial(func, *args, **kwargs))

    def bool_emojify(self, bool_var: bool) -> str:
        return "✅" if bool_var else "❌"

    async def _badge_convert_dict(self, userinfo):
        if "badges" not in userinfo or not isinstance(userinfo["badges"], dict):
            await self.db.users.update_one(
                {"user_id": userinfo["user_id"]}, {"$set": {"badges": {}}}
            )
        return await self.db.users.find_one({"user_id": userinfo["user_id"]})

    async def _rgb_to_hex(self, rgb):
        rgb = tuple(rgb[:3])
        return "#%02x%02x%02x" % rgb

    # converts hex to rgb
    async def _hex_to_rgb(self, hex_num: str, a: int):
        h = hex_num.lstrip("#")

        # if only 3 characters are given
        if len(str(h)) == 3:
            expand = "".join([x * 2 for x in str(h)])
            h = expand

        colors = [int(h[i : i + 2], 16) for i in (0, 2, 4)]
        colors.append(a)
        return tuple(colors)

    async def _process_purchase(self, ctx):
        user = ctx.author
        server = ctx.guild
        bg_price = await self.config.bg_price()

        if bg_price != 0:
            if not await bank.can_spend(user, bg_price):
                await ctx.send(
                    f"Insufficient funds. Backgrounds changes cost: "
                    f"{bg_price}{(await bank.get_currency_name(server))[0]}"
                )
                return False
            await ctx.send(
                "{}, you are about to buy a background for `{}`. Confirm by typing `yes`.".format(
                    user.mention, bg_price
                ),
                allowed_mentions=discord.AllowedMentions(users=await self.config.mention()),
            )
            pred = MessagePredicate.yes_or_no(ctx)
            try:
                await self.bot.wait_for("message", timeout=15, check=pred)
            except AsyncTimeoutError:
                pass
            if not pred.result:
                await ctx.send("Purchase canceled.")
                return False
            await bank.withdraw_credits(user, bg_price)
            return True
        return True

    def _truncate_text(self, text, max_length):
        if len(text) > max_length:
            return text[: max_length - 1] + "…"
        return text
