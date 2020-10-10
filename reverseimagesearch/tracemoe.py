from base64 import b64encode
from collections import namedtuple
from io import BytesIO
from urllib.parse import quote

from aiohttp import ClientResponseError
from PIL import Image, UnidentifiedImageError
from redbot.core.i18n import Translator

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json

_ = Translator("ReverseImageSearch", __file__)

BASE_URL = "https://trace.moe"
BASE_API_URL = f"{BASE_URL}/api"


class TraceMoeDoc:
    def __init__(self, data: dict):
        self.time_start = data.get("from")
        self.time_end = data.get("to")
        self.time = data.get("at")
        self.episode = data.get("episode")
        self.similarity = data.get("similarity")
        self.anilist_id = data.get("anilist_id")
        self.mal_id = data.get("mal_id")
        self.is_adult = data.get("is_adult")
        self.title = data.get("title")
        self.title_native = data.get("title_native")
        self.title_chinese = data.get("title_chinese")
        self.title_english = data.get("title_english")
        self.title_romaji = data.get("title_romaji")
        self.synonyms = data.get("synonyms")
        self.synonyms_chinese = data.get("synonyms_chinese")
        self.filename = data.get("filename")
        tokenthumb = data.get("tokenthumb")
        self.thumbnail = (
            f"{BASE_URL}/thumbnail.php?anilist_id={self.anilist_id}"
            f"&file={quote(self.filename)}&t={self.time}&token={tokenthumb}"
        )
        self.preview = (
            f"https://trace.moe/preview.php?anilist_id={self.anilist_id}&file="
            f"{quote(self.filename)}&t={self.time}&token={tokenthumb}"
        )
        self.preview_scene = (
            f"https://media.trace.moe/video/{self.anilist_id}/{quote(self.filename)}"
            f"?t={self.time}&token={tokenthumb}"
        )

    @property
    def time_str(self):
        hours, minutes = divmod(self.time, 3600)
        minutes, seconds = divmod(minutes, 60)
        return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))


class TraceMoe:
    def __init__(self, data: dict):
        self.searched_for = data.get("RawDocsCount")
        self.rawsearchtime = data.get("RawDocsSearchTime")
        self.comparetime = data.get("ReRankSearchTime")
        self.cached = data.get("CacheHit")
        self.times_searched = data.get("trial")
        self.limit_remain = data.get("limit")
        self.limit_reset = data.get("limit_ttl")
        self.quota_remain = data.get("quota")
        self.quota_reset = data.get("quota_ttl")
        self.docs = [TraceMoeDoc(doc) for doc in data.get("docs")]

    @classmethod
    async def from_image(cls, ctx, image_url):
        apikeys = await ctx.bot.get_shared_api_tokens("reverseimagesearch")
        apikey = apikeys.get("tracemoe", "")
        async with ctx.typing():
            try:
                async with ctx.cog.session.get(image_url, raise_for_status=True) as resp:
                    image = BytesIO(await resp.read())
                    image_file = BytesIO()
                    with Image.open(image) as pil_image:
                        with pil_image.convert("RGB") as converted:
                            converted.thumbnail((2048, 2048))
                            converted.save(image_file, "JPEG")
                            image.close()
            except UnidentifiedImageError:
                raise ValueError(_("Unable to convert image."))
            except ClientResponseError as e:
                raise ValueError(_("Unable to get image: {}").format(e.message))
            try:
                async with ctx.cog.session.post(
                    f"{BASE_API_URL}/search",
                    params={"token": apikey},
                    json={"image": b64encode(image_file.getvalue()).decode()},
                    raise_for_status=True,
                ) as data:
                    image_file.close()
                    return cls(await data.json(loads=json.loads))
            except ClientResponseError as e:
                raise ValueError(
                    _(
                        "Unable to search for provided image, trace.moe returned {status} ({message})"
                    ).format(status=e.status, message=e.message)
                )

    @classmethod
    async def me(cls, ctx):
        async with ctx.cog.session.get(f"{BASE_API_URL}/me") as data:
            data = await data.json(loads=json.loads)
        me_tuple = namedtuple(
            "me",
            "user_id, email, limit, limit_ttl, quota, "
            "quota_ttl, user_limit, user_limit_ttl, "
            "user_quota, user_quota_ttl",
        )
        return me_tuple(
            data.get("user_id"),
            data.get("email"),
            data.get("limit"),
            data.get("limit_ttl"),
            data.get("quota"),
            data.get("quota_ttl"),
            data.get("user_limit"),
            data.get("user_limit_ttl"),
            data.get("user_quota"),
            data.get("user_quota_ttl"),
        )
