import itertools
import random
import re
import string
from binascii import Error as binasciiError
from io import BytesIO
from typing import Optional
from urllib import parse

import aiohttp
import discord
import pybase64
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat

from .converters import PySupportedEncoding

try:
    from redbot import json  # support of Draper's branch
except ImportError:
    import json

_ = Translator("Translators", __file__)

USERAGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/88.0.4324.104 "
    "Safari/537.36"
)

# noinspection PyDictDuplicateKeys
EMOJIFY_CHARS = {
    "\N{DOWNWARDS ARROW}": "\N{DOWNWARDS BLACK ARROW}",
    "\N{UPWARDS ARROW}": "\N{UPWARDS BLACK ARROW}",
    "\N{LEFTWARDS ARROW}": "\N{LEFTWARDS BLACK ARROW}",
    "\N{RIGHTWARDS ARROW}": "\N{BLACK RIGHTWARDS ARROW}",
    "\N{EM DASH}": "\N{HEAVY MINUS SIGN}",
    "\N{HYPHEN-MINUS}": "\N{HEAVY MINUS SIGN}",
    "\N{FULL STOP}": "\N{BLACK CIRCLE FOR RECORD}",
    "\N{EXCLAMATION MARK}": "\N{INFORMATION SOURCE}",
}


@cog_i18n(_)
class Translators(commands.Cog):
    """Useful (and not) translators"""

    __version__ = "2.2.7"

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(json_serialize=json.dumps)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    async def red_delete_data_for_user(self, **kwargs):
        return

    @commands.command()
    async def googlesay(
        self, ctx, lang: str, *, text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Say something via Google Translate

        lang arg must be two-letters google-translate language code
        Not all languages support tts
        If text contains more than 200 symbols, it will be cut"""
        text = text[:200]
        async with ctx.typing():
            try:
                async with self.session.get(
                    "http://translate.google.com/translate_tts",
                    params={"ie": "utf-8", "q": text, "tl": lang, "client": "tw-ob"},
                    headers={"User-Agent": USERAGENT},
                    raise_for_status=True,
                ) as data:
                    speech = await data.read()
            except aiohttp.ClientResponseError as e:
                if e.status == 404:
                    await ctx.send(
                        _("Language {} is not supported or incorrect").format(lang.lower())
                    )
                else:
                    await ctx.send(
                        _("Unable to get data from Google Translate TTS: {}").format(e.status)
                    )
                return
        speechfile = BytesIO(speech)
        file = discord.File(speechfile, filename="{}.mp3".format(text[:32]))
        await ctx.send(file=file)
        speechfile.close()

    @commands.command(aliases=["ецихо"])
    async def eciho(self, ctx, *, text: commands.clean_content(fix_channel_mentions=True)):
        """Translates text (cyrillic/latin) to "eciho"

        eciho - language created by Фражуз#2170 (255682413445906433)

        This is unusable shit, i know, but whatever"""
        char = "сзчшщжуюваёяэкгфйыъьд"
        tran = "ццццццооооееехххииииб"
        table = str.maketrans(char, tran)
        text = text.translate(table)
        char = char.upper()
        tran = tran.upper()
        table = str.maketrans(char, tran)
        text = text.translate(table)
        text = "".join(c for c, _ in itertools.groupby(text))
        char = "uavwjyqkhfxdzs"
        tran = "ooooiigggggbcc"
        table = str.maketrans(char, tran)
        text = text.translate(table)
        char = char.upper()
        tran = tran.upper()
        table = str.maketrans(char, tran)
        text = text.translate(table)
        await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())

    @commands.command()
    async def fliptext(self, ctx, *, text: commands.clean_content(fix_channel_mentions=True)):
        """Flips text upside-down

        Based on https://unicode-table.com/en/tools/flip/"""
        # https://s.unicode-table.com/static/js/tools/Flip.js
        up = "abcdefghijklmnopqrstuvwxyzабвгдежзиклмнопрстуфхцчшщъьэя.,!?()[]{}_‿⁅∴"
        down = "ɐqɔpǝɟƃɥıɾʞlɯuodᕹɹsʇnʌʍxʎzɐƍʚɹɓǝжεиʞvwноudɔɯʎȸхǹҺmmqqєʁ˙‘¡¿)(][}{‾⁀⁆∵"
        text = text.casefold()
        char = up + down
        tran = down + up
        table = str.maketrans(char, tran)
        text = text.translate(table)[::-1]
        dic = {"ю": "oı", "ы": "ıq", "ё": "ǝ̤", "й": "n̯"}
        pattern = re.compile("|".join(dic.keys()))
        result = pattern.sub(lambda x: dic[x.group()], text)
        await ctx.send(result)

    @commands.command()
    async def fullwidth(self, ctx, *, text: commands.clean_content(fix_channel_mentions=True)):
        """Switches text to Ｆｕｌｌ－ｗｉｄｔｈ　ｃｈａｒａｃｔｅｒｓ"""
        halfwidth = "qwertyuiopasdfghjklzxcvbnm1234567890!?@#$%^&*()_+-=<>.,/;:'\"[]{}|\\`~ "
        fullwidth = "ｑｗｅｒｔｙｕｉｏｐａｓｄｆｇｈｊｋｌｚｘｃｖｂｎｍ１２３４５６７８９０！？＠＃＄％＾＆＊（）＿＋－＝＜＞．，／；：＇＂［］｛｝｜＼｀～　"
        table = str.maketrans(halfwidth, fullwidth)
        text = text.translate(table)
        halfwidth = halfwidth.upper()
        fullwidth = fullwidth.upper()
        table = str.maketrans(halfwidth, fullwidth)
        text = text.translate(table)
        await ctx.send(text)

    @commands.group()
    async def leet(self, ctx: commands.Context):
        """Leet (1337) translation commands"""
        pass

    @leet.command(name="leet", aliases=["1337"])
    async def _leet(self, ctx, *, text: commands.clean_content(fix_channel_mentions=True)):
        """Translates provided text to 1337"""
        text = text.upper()
        dic = {
            "A": random.choice(["/-|", "4"]),
            "B": "8",
            "C": random.choice(["(", "["]),
            "D": "|)",
            "E": "3",
            "F": random.choice(["|=", "ph"]),
            "G": "6",
            "H": "|-|",
            "I": random.choice(["|", "!", "1"]),
            "J": ")",
            "K": random.choice(["|<", "|("]),
            "L": random.choice(["|_", "1"]),
            "M": random.choice(["|\\/|", "/\\/\\"]),
            "N": random.choice(["|\\|", "/\\/"]),
            "O": random.choice(["0", "()"]),
            "P": "|>",
            "Q": random.choice(["9", "0"]),
            "R": random.choice(["|?", "|2"]),
            "S": random.choice(["5", "$"]),
            "T": random.choice(["7", "+"]),
            "U": "|_|",
            "V": "\\/",
            "W": random.choice(["\\/\\/", "\\X/"]),
            "X": random.choice(["*", "><"]),
            "Y": "'/",
            "Z": "2",
        }
        pattern = re.compile("|".join(dic.keys()))
        result = pattern.sub(lambda x: dic[x.group()], text)
        await ctx.send(chat.box(result))

    @leet.command(aliases=["russian", "cyrillic"])
    async def cs(self, ctx, *, text: commands.clean_content(fix_channel_mentions=True)):
        """Translate cyrillic to 1337"""
        text = text.upper()
        dic_cs = {
            "А": "A",
            "Б": "6",
            "В": "B",
            "Г": "r",
            "Д": random.choice(["D", "g"]),
            "Е": "E",
            "Ё": "E",
            "Ж": random.choice(["}|{", ">|<"]),
            "З": "3",
            "И": random.choice(["u", "N"]),
            "Й": "u*",
            "К": "K",
            "Л": random.choice(["JI", "/I"]),
            "М": "M",
            "Н": "H",
            "О": "O",
            "П": random.choice(["II", "n", "/7"]),
            "Р": "P",
            "С": "C",
            "Т": random.choice(["T", "m"]),
            "У": random.choice(["Y", "y"]),
            "Ф": random.choice(["cp", "(|)", "qp"]),
            "Х": "X",
            "Ц": random.choice(["U", "LL", "L|"]),
            "Ч": "4",
            "Ш": random.choice(["W", "LLI"]),
            "Щ": random.choice(["W", "LLL"]),
            "Ъ": random.choice(["~b", "`b"]),
            "Ы": "bl",
            "Ь": "b",
            "Э": "-)",
            "Ю": random.choice(["IO", "10"]),
            "Я": random.choice(["9", "9I"]),
            "%": "o\\o",
        }
        pattern = re.compile("|".join(dic_cs.keys()))
        result = pattern.sub(lambda x: dic_cs[x.group()], text)
        await ctx.send(chat.box(result))

    @commands.group(name="base64")
    async def base64_command(self, ctx):
        """Base64 text converter"""
        pass

    @base64_command.command(name="encode")
    async def tobase64(self, ctx, encoding: Optional[PySupportedEncoding], *, text: str):
        """Encode text to Base64"""
        if not encoding:
            encoding = "utf-8"
        try:
            text = text.encode(encoding=encoding, errors="replace")
        except UnicodeError:
            await ctx.send(
                chat.error(
                    _("Unable to encode provided string to `{}` encoding.").format(encoding)
                )
            )
            return
        output = pybase64.standard_b64encode(text)
        result = output.decode()
        for page in chat.pagify(result):
            await ctx.send(chat.box(page))

    @base64_command.command(name="decode")
    async def frombase64(self, ctx, encoding: Optional[PySupportedEncoding], *, encoded: str):
        """Decode text from Base64"""
        if not encoding:
            encoding = "utf-8"
        encoded = encoded + "=="  # extra padding if padding is missing from string
        encoded = encoded.encode()
        try:
            decoded = pybase64.standard_b64decode(encoded)
        except binasciiError:
            await ctx.send(chat.error(_("Invalid Base64 string provided")))
            return
        try:
            result = decoded.decode(encoding=encoding, errors="replace")
        except UnicodeError:
            await ctx.send(
                chat.error(
                    _("Unable to decode provided string from `{}` encoding.").format(encoding)
                )
            )
            return
        await ctx.send(chat.box(result))

    @commands.command()
    async def emojify(self, ctx, *, message: commands.clean_content(fix_channel_mentions=True)):
        """Emojify text"""
        table = str.maketrans("".join(EMOJIFY_CHARS.keys()), "".join(EMOJIFY_CHARS.values()))
        message = message.translate(table)
        message = "".join(
            map(
                lambda c: f":regional_indicator_{c.lower()}:" if c in string.ascii_letters else c,
                message,
            )
        )
        message = "".join(
            map(
                lambda c: f"{c}\N{COMBINING ENCLOSING KEYCAP}" if c in string.digits else c,
                message,
            )
        )
        message = (
            message.replace(" ", "　　")
            .replace("#", "#\N{COMBINING ENCLOSING KEYCAP}")
            .replace("*", "*\N{COMBINING ENCLOSING KEYCAP}")
        )
        await ctx.send(
            message,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @commands.group()
    async def url(self, ctx):
        """Encode or decode text in URL-format ("%20"-format)"""
        pass

    @url.command(name="encode")
    async def url_encode(self, ctx, encoding: Optional[PySupportedEncoding], *, text: str):
        """Encode text to url-like format
        'abc def' -> 'abc%20def'"""
        if not encoding:
            encoding = "utf-8"
        try:
            encoded_url = parse.quote(text, encoding=encoding, errors="replace")
        except UnicodeError:
            await ctx.send(
                chat.error(
                    _("Unable to encode provided string to `{}` encoding.").format(encoding)
                )
            )
            return
        await ctx.send(chat.box(encoded_url))

    @url.command(name="decode")
    async def url_decode(
        self, ctx, encoding: Optional[PySupportedEncoding], *, url_formatted_text: str
    ):
        """Decode text from url-like format
        'abc%20def' -> 'abc def'"""
        if not encoding:
            encoding = "utf-8"
        try:
            decoded_text = parse.unquote(url_formatted_text, encoding=encoding)
        except UnicodeError:
            await ctx.send(
                chat.error(
                    _("Unable to decode provided string from `{}` encoding.").format(encoding)
                )
            )
            return
        await ctx.send(chat.box(decoded_text))
