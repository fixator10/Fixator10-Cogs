from datetime import datetime, timedelta

from aiohttp import ClientResponseError
from bs4 import BeautifulSoup
from redbot.core.commands import BadArgument
from redbot.core.i18n import Translator

_ = Translator("SMMData", __file__)

BASE_URL = "https://supermariomakerbookmark.nintendo.net"


class SMMB:
    class Level:
        """SuperMarioMaker Bookmark Level"""

        # based on JS lib by jacobjordan94 (thanks for css classnames)
        # https://github.com/jacobjordan94/mario-maker/blob/master/mario-maker.js

        def __init__(self, data: BeautifulSoup):
            self._data = data
            self.url = data.find("meta", property="og:url").get("content")
            self.difficulty = data.select_one(".course-header").get_text(strip=True)
            self.title = data.select_one(".course-title").string
            tag = data.select_one(".course-meta-info > .course-tag").string
            self.tag = tag if tag != "---" else None
            self.preview = data.select_one(".course-image > .course-image").get("src")
            self.map = data.select_one(".course-image-full").get("src")
            self.creator = data.select_one(".creator-info > .name").string
            self.creator_url = BASE_URL + data.select_one(
                ".mii-wrapper.creator > .link"
            ).get("href")
            self.creator_img = data.select_one(
                ".mii-wrapper.creator > .link > img"
            ).get("src")
            self.best_player = data.select_one(
                ".fastest-time-wrapper > .user-wrapper > .user-info > .name"
            ).string
            self.best_player_url = BASE_URL + data.select_one(
                ".fastest-time-wrapper > .user-wrapper > .mii-wrapper > .link"
            ).get("href")
            self.best_player_img = data.select_one(
                ".fastest-time-wrapper > .user-wrapper > .mii-wrapper > .link > img"
            ).get("src")
            self.first_clear_name = data.select_one(
                ".first-user > .body > .user-wrapper > .user-info > .name"
            ).string
            self.first_clear_url = BASE_URL + data.select_one(
                ".first-user > .body > .user-wrapper > .mii-wrapper > .link"
            ).get("href")
            self.first_clear_img = data.select_one(
                ".first-user > .body > .user-wrapper > .mii-wrapper > .link > img"
            ).get("src")

        @property
        def created_at(self):
            created_at = self._data.select_one(".created_at").string
            if "ago" in created_at:
                created_at_ago = int(created_at.split()[0])
                if "hour" in created_at:
                    created_at = datetime.utcnow() - timedelta(hours=created_at_ago)
                elif "day" in created_at:
                    created_at = datetime.utcnow() - timedelta(days=created_at_ago)
            else:
                created_at = created_at.split("/")
                created_at = datetime(
                    int(created_at[2]), int(created_at[0]), int(created_at[1])
                )  # [MM, DD, YYYY]
            return created_at

        @property
        def clear_rate(self):
            clear_rate = ""
            for char in self._data.select(".clear-rate > .typography"):
                char = char.get("class", "")[1].replace("typography-", "")
                if char.isdigit():
                    clear_rate += char
                elif char == "second":
                    clear_rate += "."
            clear_rate = float(clear_rate)
            return clear_rate

        @property
        def best_player_time(self):
            clear_time = ""
            for char in self._data.select(
                    ".fastest-time-wrapper > .clear-time > .typography"
            ):
                char = char.get("class", "")[1].replace("typography-", "")
                if char.isdigit():
                    clear_time += char
                elif char == "minute":
                    clear_time += ":"
                elif char == "second":
                    clear_time += "."
            return clear_time

        @property
        def stars(self):
            return self._cleanup_typography_int(".liked-count > .typography")

        @property
        def players(self):
            return self._cleanup_typography_int(".played-count > .typography")

        @property
        def shares(self):
            return self._cleanup_typography_int(".shared-count > .typography")

        @property
        def clears(self):
            return self._cleanup_typography_int(
                ".tried-count > .typography", split="slash"
            )[0]

        @property
        def attempts(self):
            return self._cleanup_typography_int(
                ".tried-count > .typography", split="slash"
            )[1]

        @property
        def difficulty_color(self):
            if self.difficulty == "Easy":
                return 0x28AD8A
            if self.difficulty == "Normal":
                return 0x2691BC
            if self.difficulty == "Expert":
                return 0xEA348B
            if self.difficulty == "Super Expert":
                return 0xFF4545

        @classmethod
        async def convert(cls, ctx, argument):
            async with ctx.typing():
                try:
                    async with ctx.cog.session.get(
                            f"{BASE_URL}/courses/{argument}", raise_for_status=True
                    ) as page:
                        return cls(BeautifulSoup(await page.read(), "html"))
                except ClientResponseError as e:
                    raise BadArgument(
                        _("Unable to find level {level}: {status}").format(
                            level=argument, status=e.message
                        )
                    )

        def _cleanup_typography_int(
                self, selector: str, split: str = None
        ) -> (str, list):
            """Returns string from typography css class

            :param selector: css selector with typography
            :param split: css class name without "typography-", which will be used as separator"""
            numbers = ""
            for char in self._data.select(selector):
                char = char.get("class", "")[1].replace("typography-", "")
                if char.isdigit():
                    numbers += char
                if char == split:
                    numbers += split
            numbers = numbers.split(split)
            if len(numbers) == 1:
                numbers = int(numbers[0])
            return numbers
