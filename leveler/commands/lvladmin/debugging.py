from collections import Counter

from motor import version as motorversion
from PIL import features as pilfeatures
from pymongo import version as pymongoversion
from redbot.core import commands
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as chat
from tabulate import tabulate

from leveler.abc import MixinMeta

from .basecmd import LevelAdminBaseCMD


class Debugging(MixinMeta):
    """Debug commands"""

    lvladmin = getattr(LevelAdminBaseCMD, "lvladmin")

    @lvladmin.group(hidden=True, name="debug")
    @commands.is_owner()
    async def debug_commands(self, ctx):
        """Debug commands.

        Dont use it until you know what you doing."""

    @debug_commands.command(name="info")
    async def debug_info(self, ctx):
        """Get info about libs used by leveler and environment info"""
        await ctx.send(
            chat.box(
                tabulate(
                    [
                        ("DB lock locked", self._db_lock.locked()),
                        (
                            "DB lock queue",
                            "N/A"
                            if self._db_lock._waiters is None
                            else len(self._db_lock._waiters),
                        ),
                        ("pymongo version", pymongoversion),
                        ("motor version", motorversion),
                        (
                            "Mongo DB version",
                            (await self.client.server_info()).get("version", "?"),
                        ),
                        ("PIL version", pilfeatures.version("pil")),
                        (
                            "PIL features",
                            tabulate(
                                [
                                    (feature, pilfeatures.version(feature) or "N/A")
                                    for feature in pilfeatures.get_supported()
                                ],
                                tablefmt="psql",
                            ),
                        ),
                    ],
                    tablefmt="psql",
                )
            )
        )

    @debug_commands.group(name="database", aliases=["db"])
    async def db_commands(self, ctx):
        """Database debug commands"""

    @db_commands.command(name="duplicates", aliases=["dupes"])
    async def db_duplicates(self, ctx):
        """Show users that have more than one document in database"""
        dupes = await self.db.users.aggregate(
            [
                {
                    "$group": {
                        "_id": "$user_id",
                        "doc_ids": {"$addToSet": "$_id"},
                        "count": {"$sum": 1},
                    }
                },
                {"$match": {"count": {"$gt": 1}}},
            ]
        ).to_list(None)
        if not dupes:
            await ctx.send(chat.info("No duplicates found."))
            return
        async for u in AsyncIter(dupes):
            u["doc_ids"] = "\n".join(map(str, u["doc_ids"]))
        await ctx.send_interactive(
            chat.pagify(
                tabulate(
                    dupes,
                    headers={"_id": "User ID", "doc_ids": "DB document _id", "count": "Count"},
                ),
                page_length=1992,
            ),
            box_lang="",
        )

    @db_commands.group(name="integrity")
    async def db_integrity(self, ctx):
        """Database integrity commands."""

    @db_integrity.command(name="check")
    async def db_integrity_check(self, ctx):
        """Check Database integrity.

        Everything should be True. Otherwise there is malfunction somewhere in XP handling."""
        c = Counter()
        invalid_users = []
        async with ctx.typing():
            async for user in self.db.users.find({}):
                total_xp = 0
                for server in user["servers"]:
                    xp = await self._level_exp(user["servers"][server]["level"])
                    total_xp += xp
                    total_xp += user["servers"][server]["current_exp"]
                valid = total_xp == user["total_exp"]
                c[valid] += 1
                if not valid:
                    invalid_users.append(
                        (
                            user["username"],
                            user["user_id"],
                            total_xp,
                            user["total_exp"],
                            user["total_exp"] - total_xp,
                        )
                    )
        await ctx.send(chat.box(tabulate(c.most_common())))
        if invalid_users:
            await ctx.send_interactive(
                chat.pagify(
                    tabulate(
                        invalid_users,
                        headers=["Username", "ID", "Calculated total XP", "Total XP", "Diff"],
                    ),
                    page_length=1992,
                ),
                box_lang="",
            )

    @db_integrity.command(name="fix")
    async def db_integrity_fix(self, ctx):
        """Artificially fix Database integrity."""
        async with ctx.typing():
            async for user in self.db.users.find({}):
                total_xp = 0
                for server in user["servers"]:
                    xp = await self._level_exp(user["servers"][server]["level"])
                    total_xp += xp
                    total_xp += user["servers"][server]["current_exp"]
                if total_xp != user["total_exp"]:
                    await self.db.users.update_one(
                        {"user_id": user["user_id"]}, {"$set": {"total_exp": total_xp}}
                    )
        await ctx.tick()
