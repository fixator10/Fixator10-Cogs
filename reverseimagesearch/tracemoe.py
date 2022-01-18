from collections import namedtuple
from io import BytesIO

from aiohttp import ClientResponseError, FormData
from PIL import Image, UnidentifiedImageError
from redbot.core.i18n import Translator

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json

_ = Translator("ReverseImageSearch", __file__)

BASE_URL = "https://trace.moe"
BASE_API_URL = f"https://api.trace.moe"


class TraceMoeDoc:
    def __init__(self, data: dict):
        self.time_start = data.get("from")
        self.time_end = data.get("to")
        self.episode = data.get("episode")
        self.similarity = data.get("similarity")
        if isinstance(anilist := data.get("anilist"), dict):
            self.anilist_id = anilist.get("id")
            self.mal_id = anilist.get("idMal")
            self.is_adult = anilist.get("isAdult")
            self.title = anilist.get("title", {}).get("native")
            self.title_romaji = anilist.get("title", {}).get("romaji")
            self.title_english = anilist.get("title", {}).get("english")
            self.synonyms = anilist.get("synonyms", [])
        else:
            self.anilist_id = anilist
            self.mal_id = None
            self.is_adult = None
            self.title = None
            self.title_romaji = None
            self.title_english = None
            self.synonyms = None
        self.filename = data.get("filename")
        self.image = data.get("image")
        self.video = data.get("video")

    @property
    def time_str(self):
        s_hours, s_minutes = divmod(self.time_start, 3600)
        s_minutes, s_seconds = divmod(s_minutes, 60)
        e_hours, e_minutes = divmod(self.time_end, 3600)
        e_minutes, e_seconds = divmod(e_minutes, 60)
        return (
            "{:02}:{:02}:{:02} - {:02}:{:02}:{:02}\n".format(
                int(s_hours),
                int(s_minutes),
                int(s_seconds),
                int(e_hours),
                int(e_minutes),
                int(e_seconds),
            )
            + f"{self.time_start, self.time_end}"
        )


class TraceMoe:
    def __init__(self, data: dict):
        self.searched_for = data.get("frameCount")
        self.docs = [TraceMoeDoc(doc) for doc in data.get("result")]

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
                            image_file.seek(0)
                            image.close()
            except UnidentifiedImageError:
                raise ValueError(_("Unable to convert image."))
            except ClientResponseError as e:
                raise ValueError(_("Unable to get image: {}").format(e.message))
            try:
                data = FormData()
                data.add_field("image", image_file, filename="image.jpg")
                async with ctx.cog.session.post(
                    f"{BASE_API_URL}/search",
                    headers={"x-trace-key": apikey} if apikey else None,
                    params={"anilistInfo": ""},
                    data=data,
                ) as data:
                    # image file closed by aiohttp
                    resp = await data.json(loads=json.loads)
                    if data.status != 200 or (error := resp.get("error")):
                        raise ValueError(
                            _("An error occurred during search: {}").format(
                                error or f"{data.status} ({data.reason})"
                            )
                        )
                    return cls(resp)
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
            "user_id,priority,concurrency,quota,quotaUsed",
        )
        return me_tuple(
            data.get("id"),
            data.get("priority"),
            data.get("concurrency"),
            data.get("quota"),
            data.get("quotaUsed"),
        )
