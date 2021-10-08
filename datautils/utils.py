from redbot.core.i18n import Translator
from redbot.core.utils import AsyncIter

from .common_variables import TWEMOJI_URL

_ = Translator("DataUtils", __file__)


async def get_twemoji(emoji: str):
    emoji_unicode = []
    for char in emoji:
        char = hex(ord(char))[2:]
        emoji_unicode.append(char)
    if "200d" not in emoji_unicode:
        emoji_unicode = list(filter(lambda c: c != "fe0f", emoji_unicode))
    emoji_unicode = "-".join(emoji_unicode)
    return f"{TWEMOJI_URL}/{emoji_unicode}.png"


async def find_app_by_name(where: list, name: str):
    async for item in AsyncIter(where):
        for k, v in item.items():
            if v == name:
                return item
