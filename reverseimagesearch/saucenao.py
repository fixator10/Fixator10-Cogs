import re
from types import SimpleNamespace

from aiohttp import ClientResponseError
from dateutil.parser import parse
from redbot.core.i18n import Translator
from yarl import URL

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json

_ = Translator("ReverseImageSearch", __file__)

BASE_API_URL = "https://saucenao.com/search.php"
INDEX_SERVICENAME_REGEX = re.compile(r"^Index #\d*: (?P<service>.*) - [^ ]*\.jpg$")


class SauceNAOEntry:
    def __init__(self, result: dict):
        header = result.get("header", {})
        self.similarity = header.get("similarity")
        self.thumbnail = URL(header.get("thumbnail"))
        self.index = SimpleNamespace()
        self.index.id = header.get("index_id")
        self.index.name = header.get("index_name")
        data = result.get("data", {})
        self.urls = data.get("ext_urls", [])
        self.title = data.get("title")
        self.created_at = parse(data.get("created_at")) if data.get("created_at") else None
        self.member_name = (
            data.get("member_name") or data.get("author_name") or data.get("pawoo_user_username")
        )
        self.creator = data.get("creator")
        self.material = data.get("material")
        self.characters = data.get("characters")
        self.source = data.get("source")
        self.eng_name = data.get("eng_name")
        self.jp_name = data.get("jp_name")
        self.part = data.get("part")
        self.type = data.get("type")
        self.year = data.get("year")
        self.est_time = data.get("est_time")

    @property
    def service(self):
        match = re.match(INDEX_SERVICENAME_REGEX, self.index.name)
        if match:
            return match.group("service")
        return


class SauceNAO:
    def __init__(self, apidata: dict):
        header = apidata.get("header")
        self.user_id = header.get("user_id")
        self.account_type = header.get("account_type")
        self.limits = SimpleNamespace()
        self.limits.short = header.get("short_limit", 0)
        self.limits.long = header.get("long_limit", 0)
        self.limits.remaining = SimpleNamespace()
        self.limits.remaining.short = header.get("short_remaining", 0)
        self.limits.remaining.long = header.get("long_remaining", 0)
        self.status = header.get("status")
        self.results_requested = header.get("results_requested")
        # self.index = header.get("index", [{}])
        self.depth = header.get("search_depth")
        self.minimum_similarity = header.get("minimum_similarity")
        self.query_image_display = header.get("query_image_display")
        self.query_image = header.get("query_image")
        self.results_returned = header.get("results_returned")
        self.results = [SauceNAOEntry(result) for result in apidata.get("results", [])]

    @classmethod
    async def from_image(cls, ctx, image_url):
        apikeys = await ctx.bot.get_shared_api_tokens("reverseimagesearch")
        apikey = apikeys.get("saucenao", "")
        params = {
            "output_type": 2,  # JSON API
            "api_key": apikey,
            "test_mode": 1,
            "db": 999,
            "numres": await ctx.cog.config.numres(),
            "url": image_url,
        }
        async with ctx.typing():
            try:
                async with ctx.cog.session.get(
                    BASE_API_URL, params=params, raise_for_status=True
                ) as data:
                    data = await data.json(loads=json.loads)
                    if data.get("status", 0) != 0:
                        if data.get("status") > 0:
                            raise ValueError(
                                _(
                                    "Unable to search for provided image, SauceNAO returned {status} ({message})\n"
                                    "This is server issue, try again later."
                                ).format(
                                    status=data.get("status"),
                                    message=data.get("message"),
                                )
                            )
                        raise ValueError(
                            _(
                                "Unable to search for provided image, SauceNAO returned {status} ({message})"
                            ).format(status=data.get("status"), message=data.get("message"))
                        )
                    return cls(data)
            except ClientResponseError as e:
                raise ValueError(
                    _(
                        "Unable to search for provided image, SauceNAO returned {status} ({message})"
                    ).format(status=e.status, message=e.message)
                )
