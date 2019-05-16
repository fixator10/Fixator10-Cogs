import base64
import itertools
import random
import re
from io import BytesIO
from urllib import parse

import aiohttp
import discord
from redbot.core import checks
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import chat_formatting as chat

from . import yandextranslate

_ = Translator("Translators", __file__)

USERAGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Ubuntu Chromium/69.0.3497.81 "
    "Chrome/69.0.3497.81 "
    "Safari/537.36"
)


@cog_i18n(_)
class Translators(commands.Cog):
    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    @commands.command()
    @checks.is_owner()
    async def ytapikey(self, ctx):
        """Set API key for Yandex.Translate"""
        message = _(
            "To get Yandex.Translate API key:\n"
            "1. Login to your Yandex account\n"
            "1.1. Visit [API keys](https://translate.yandex.com/developers/keys) page\n"
            "2. Press `Create a new key`\n"
            "3. Enter description for key\n"
            "4. Copy `trnsl.*` key\n"
            "5. Use `{}set api yandex translate,<your_apikey>`"
        ).format(ctx.prefix)
        await ctx.maybe_send_embed(message)

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def ytranslate(self, ctx, language: str, *, text: str):
        """Translate text via Yandex

        Language may be just "ru" (target language to translate)
        or "en-ru" (original text's language - target language)"""
        text = chat.escape(text, formatting=True)
        apikeys = await self.bot.db.api_tokens.get_raw(
            "yandex", default={"translate": None}
        )
        try:
            translator = yandextranslate.YTranslateAPI(
                self.session, apikeys["translate"]
            )
            translation = await translator.get_translation(language, text)
        except yandextranslate.Exceptions.IncorrectLang:
            await ctx.send(
                chat.error(
                    _(
                        "An error has been occurred: "
                        "Language {} is not supported or incorrect, "
                        "check your formatting and try again"
                    ).format(chat.inline(language))
                )
            )
        except yandextranslate.Exceptions.MaxTextLengthExceeded:
            await ctx.send(
                chat.error(
                    _(
                        "An error has been occurred: Text that you provided is too big to translate"
                    )
                )
            )
        except yandextranslate.Exceptions.KeyBlocked:
            await ctx.send(
                chat.error(
                    _(
                        "API key is blocked. Bot owner needs to get new api key or unlock current."
                    )
                )
            )
        except yandextranslate.Exceptions.DailyLimitExceeded:
            await ctx.send(
                chat.error(_("Daily requests limit reached. Try again later."))
            )
        except yandextranslate.Exceptions.UnableToTranslate:
            await ctx.send(
                chat.error(
                    _(
                        "An error has been occurred: Yandex.Translate is unable to translate your text"
                    )
                )
            )
        except yandextranslate.Exceptions.UnknownException as e:
            await ctx.send(chat.error(_("An error has been occurred: {}").format(e)))
        else:
            embed = discord.Embed(
                description=f"**[{translation.lang.upper()}]**{chat.box(translation.text)}",
                color=await ctx.embed_color(),
            )
            embed.set_author(
                name=_("Translated via Yandex.Translate"),
                url="https://translate.yandex.com",
                icon_url="https://translate.yandex.ru/icons/favicon.png",
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def googlesay(self, ctx, lang: str, *, text: str):
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
                        _("Language {} is not supported or incorrect").format(
                            lang.lower()
                        )
                    )
                else:
                    await ctx.send(
                        _("Unable to get data from Google Translate TTS: {}").format(
                            e.status
                        )
                    )
                return
        speechfile = BytesIO(speech)
        file = discord.File(speechfile, filename="{}.mp3".format(text[:32]))
        await ctx.send(file=file)
        speechfile.close()

    @commands.command(aliases=["ецихо"])
    async def eciho(self, ctx, *, text: str):
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
        await ctx.send(text)

    @commands.command()
    async def fliptext(self, ctx, *, text: str):
        """Flips text upside-down

        Based on https://unicode-table.com/en/tools/flip/"""
        up = "abcdefghijklmnopqrstuvwxyzабвгдежзиклмнопрстуфхцчшщъьэя.,!?()"
        down = "ɐqɔpǝɟƃɥıɾʞlɯuodᕹɹsʇnʌʍxʎzɐƍʚɹɓǝжεиʞvwноudɔɯʎȸхǹҺmmqqєʁ˙‘¡¿)("
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
    async def fullwidth(self, ctx, *, text: str):
        """Switches text to Ｆｕｌｌ－ｗｉｄｔｈ　ｃｈａｒａｃｔｅｒｓ"""
        halfwidth = (
            "qwertyuiopasdfghjklzxcvbnm1234567890!?" "@#$%^&*()_+-=<>.,/;:'\"[]{}|\\`~ "
        )
        fullwidth = (
            "ｑｗｅｒｔｙｕｉｏｐａｓｄｆｇｈｊｋｌｚｘｃｖｂｎｍ１２３４５６７８９０！？" "＠＃＄％＾＆＊（）＿＋－＝＜＞．，／；：＇＂［］｛｝｜＼｀～　"
        )
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
    async def _leet(self, ctx, *, text: str):
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
    async def cs(self, ctx, *, text: str):
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
    async def _base64(self, ctx):
        """Base64 text converter"""
        pass

    @_base64.command(name="encode")
    async def _tobase64(self, ctx, *, text: str):
        """Encode text to Base64"""
        text = text.encode()
        output = base64.standard_b64encode(text)
        result = output.decode()
        for page in chat.pagify(result):
            await ctx.send(chat.box(page))

    @_base64.command(name="decode")
    async def _frombase64(self, ctx, *, encoded: str):
        """Decode text from Base64"""
        encoded = encoded.encode()
        try:
            decoded = base64.standard_b64decode(encoded)
            result = decoded.decode()
        except Exception as e:
            await ctx.send(e)
            return
        await ctx.send(chat.box(result))

    # noinspection PyPep8
    @commands.command()
    async def emojify(self, ctx, *, message: str):
        """Emojify text"""
        char = "abcdefghijklmnopqrstuvwxyz↓↑←→—.!"
        tran = "🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯🇰🇱🇲🇳🇴🇵🇶🇷🇸🇹🇺🇻🇼🇽🇾🇿⬇⬆⬅➡➖⏺ℹ"
        table = str.maketrans(char, tran)
        name = message.translate(table)
        char = char.upper()
        table = str.maketrans(char, tran)
        name = name.translate(table)
        await ctx.send(
            name.replace(" ", "　　")
            .replace("", "​")
            .replace("0", ":zero:")
            .replace("1", ":one:")
            .replace("2", ":two:")
            .replace("3", ":three:")
            .replace("4", ":four:")
            .replace("5", ":five:")
            .replace("6", ":six:")
            .replace("7", ":seven:")
            .replace("8", ":eight:")
            .replace("9", ":nine:")
            .replace("#", "#⃣")
            .replace("*", "*⃣")
        )

    @commands.command(pass_context=True, name="urlencode", aliases=["url"])
    async def _urlencode(self, ctx, *, text: str):
        """Encode text to url-like format
        ('abc def') -> 'abc%20def'"""
        encoded_url = parse.quote(text)
        await ctx.send(chat.box(encoded_url))
