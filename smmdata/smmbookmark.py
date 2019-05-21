from collections import namedtuple
from datetime import datetime, timedelta

from aiohttp import ClientResponseError
from bs4 import BeautifulSoup
from redbot.core.commands import BadArgument
from redbot.core.i18n import Translator

_ = Translator("SMMData", __file__)

SMMB_BASE_URL = "https://supermariomakerbookmark.nintendo.net"


def _cleanup_typography_int(data, selector: str, split: str = None) -> (int, list):
    """Returns string from typography css class

    :param data: BeautifulSoup object
    :param selector: css selector with typography
    :param split: css class name without "typography-", which will be used as separator"""
    numbers = ""
    for char in data.select(selector):
        char = char.get("class", "")[1].replace("typography-", "")
        if char.isdigit():
            numbers += char
        if char == split:
            numbers += split
    numbers = numbers.split(split)
    if len(numbers) == 1:
        numbers = int(numbers[0])
    return numbers


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
        self.creator_url = SMMB_BASE_URL + data.select_one(
            ".mii-wrapper.creator > .link"
        ).get("href")
        self.creator_img = data.select_one(".mii-wrapper.creator > .link > img").get(
            "src"
        )
        if data.select_one(
                ".fastest-time-wrapper > .user-wrapper > .mii-wrapper > .link"
        ):
            self.best_player_name = data.select_one(
                ".fastest-time-wrapper > .user-wrapper > .user-info > .name"
            ).string
            self.best_player_url = SMMB_BASE_URL + data.select_one(
                ".fastest-time-wrapper > .user-wrapper > .mii-wrapper > .link"
            ).get("href")
            self.best_player_img = data.select_one(
                ".fastest-time-wrapper > .user-wrapper > .mii-wrapper > .link > img"
            ).get("src")
        else:
            self.best_player_name = None
            self.best_player_url = None
            self.best_player_img = None
        if data.select_one(
                ".first-user > .body > .user-wrapper > .mii-wrapper > .link"
        ):
            self.first_clear_name = data.select_one(
                ".first-user > .body > .user-wrapper > .user-info > .name"
            ).string
            self.first_clear_url = SMMB_BASE_URL + data.select_one(
                ".first-user > .body > .user-wrapper > .mii-wrapper > .link"
            ).get("href")
            self.first_clear_img = data.select_one(
                ".first-user > .body > .user-wrapper > .mii-wrapper > .link > img"
            ).get("src")
        else:
            self.first_clear_name = None
            self.first_clear_url = None
            self.first_clear_img = None
        self.stars = _cleanup_typography_int(data, ".liked-count > .typography")
        self.players = _cleanup_typography_int(data, ".played-count > .typography")
        self.shares = _cleanup_typography_int(data, ".shared-count > .typography")
        self.clears = _cleanup_typography_int(
            data, ".tried-count > .typography", split="slash"
        )[0]
        self.attempts = _cleanup_typography_int(
            data, ".tried-count > .typography", split="slash"
        )[1]

    @property
    def gameskin(self):
        gameskin = self._data.select_one(".gameskin").get("class", ["", "", ""])[2]
        if gameskin == "common_gs_sb":
            return "Super Mario Bros."
        if gameskin == "common_gs_sb3":
            return "Super Mario Bros. 3"
        if gameskin == "common_gs_sw":
            return "Super Mario World"
        if gameskin == "common_gs_sbu":
            return "New Super Mario Bros. U"
        return

    @property
    def created_at(self) -> datetime:
        created_at = self._data.select_one(".created_at").string
        if "ago" in created_at:
            created_at_ago = int(created_at.split()[0])
            if "hour" in created_at:
                created_at = datetime.utcnow() - timedelta(hours=created_at_ago)
            elif "day" in created_at:
                created_at = datetime.utcnow() - timedelta(days=created_at_ago)
            elif "min" in created_at:
                created_at = datetime.utcnow() - timedelta(minutes=created_at_ago)
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
        if clear_rate:
            clear_rate = float(clear_rate)
        return clear_rate or 0.0

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
    def difficulty_color(self):
        if self.difficulty == "Easy":
            return 0x28AD8A
        if self.difficulty == "Normal":
            return 0x2691BC
        if self.difficulty == "Expert":
            return 0xEA348B
        if self.difficulty == "Super Expert":
            return 0xFF4545
        return 0xF9CF00

    @classmethod
    async def convert(cls, ctx, argument):
        async with ctx.typing():
            try:
                async with ctx.cog.session.get(
                        f"{SMMB_BASE_URL}/courses/{argument}", raise_for_status=True
                ) as page:
                    return cls(BeautifulSoup(await page.read(), "html.parser"))
            except ClientResponseError as e:
                raise BadArgument(
                    _("Unable to find level {level}: {status}").format(
                        level=argument, status=e.message
                    )
                )


class Maker:
    def __init__(self, data: BeautifulSoup):
        self._data = data
        self.url = data.find("meta", property="og:url").get("content")
        self.name = data.select_one(".user-info > .name").string
        self.image = data.select_one(".mii").get("src")
        self.country = data.select_one(".user-info > .flag").get("class")[1].lower()
        self.stars = _cleanup_typography_int(
            self._data, ".star > .liked-count > .typography"
        )
        challenge = namedtuple("challenge", "easy, normal, expert, super_expert")
        self.challenge = challenge(
            self.parsetable("Easy clears"),
            self.parsetable("Normal clears"),
            self.parsetable("Expert clears"),
            self.parsetable("Super Expert clears"),
        )
        statistics = namedtuple("statistics", "played, cleared, total, lives")
        self.statistics = statistics(
            self.parsetable("Courses played"),
            self.parsetable("Courses cleared"),
            self.parsetable("Total plays"),
            self.parsetable("Lives lost"),
        )
        self.uploads = _cleanup_typography_int(
            self._data, ".user-courses-wrapper > .typography"
        )

    @property
    def medals(self) -> int:
        if self._data.select_one(".medal-count"):
            return _cleanup_typography_int(self._data, ".medal-count > .typography")
        medals = [
            m
            for m in self._data.select(".medal.bg-image")
            if m.get("class")[2] != "profile_icon_medal_non"
        ]
        if medals:
            return len(medals)
        return 0

    @classmethod
    async def convert(cls, ctx, argument):
        async with ctx.typing():
            try:
                async with ctx.cog.session.get(
                        f"{SMMB_BASE_URL}/profile/{argument}", raise_for_status=True
                ) as page:
                    return cls(BeautifulSoup(await page.read(), "html.parser"))
            except ClientResponseError as e:
                if e.status == 404:
                    raise BadArgument(_("The specified user could not be found."))
                raise BadArgument(
                    _("Unable to find user {user}: {status}").format(
                        user=argument, status=e.message
                    )
                )

    def parsetable(self, line: str):
        """Parses line in table of profile

        :param line: name of line"""
        numbers = ""
        typograhpies = [
            x for x in self._data.find(string=line).next if x.get("class") is not None
        ]
        for char in typograhpies:
            char = char.get("class", "")[1].replace("typography-", "")
            if char.isdigit():
                numbers += char
        numbers = int(numbers)
        return numbers
