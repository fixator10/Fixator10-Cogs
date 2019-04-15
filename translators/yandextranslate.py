from collections import namedtuple

import aiohttp


class Exceptions:
    class UnknownException(Exception):
        pass

    class InvalidKey(Exception):
        pass

    class KeyBlocked(Exception):
        pass

    class DailyLimitExceeded(Exception):
        pass

    class MaxTextLengthExceeded(Exception):
        pass

    class UnableToTranslate(Exception):
        pass

    class IncorrectLang(Exception):
        pass


class YTranslateAPI:
    def __init__(self, session: aiohttp.ClientSession, apikey: str):
        """Creates API wrapper object
        :param session: client session
        :param apikey: Yandex.Translate API key"""
        self.apikey = apikey
        self.session = session

    async def _make_request(self, endpoint: str, **params):
        """Make request to Yandex.Translate API"""
        params.update({"key": self.apikey})
        async with self.session.get(
            f"https://translate.yandex.net/api/v1.5/tr.json/{endpoint}", params=params
        ) as response:
            return await response.json()

    async def get_lang_list(self):
        raise NotImplementedError

    async def detect_language(self, text: str, *, hint: list = None):
        """Detect language of text
        :param text: text to detect language
        :param hint: list of most likely possible languages"""
        response = await self._make_request("detect", text=text, hint=hint)
        code = response.get("code", 0)
        if code != 200:
            message = response.get("message")
            if code == 401:
                raise Exceptions.InvalidKey(message)
            if code == 402:
                raise Exceptions.KeyBlocked(message)
            if code == 404:
                raise Exceptions.DailyLimitExceeded(message)
            raise Exceptions.UnknownException(message)
        return response.get("lang", "")

    async def get_translation(self, lang: str, text: str):
        """Get translation for list of strings
        :param lang: language in format "fr-to" or "to"
        :param text: string to translate"""
        response = await self._make_request("translate", text=text, lang=lang)
        code = response.get("code", 0)
        if code != 200:
            message = response.get("message")
            if code == 401:
                raise Exceptions.InvalidKey(message)
            if code == 402:
                raise Exceptions.KeyBlocked(message)
            if code == 404:
                raise Exceptions.DailyLimitExceeded(message)
            if code == 413:
                raise Exceptions.MaxTextLengthExceeded(message)
            if code == 422:
                raise Exceptions.UnableToTranslate(message)
            if code == 501:
                raise Exceptions.IncorrectLang(message)
            raise Exceptions.UnknownException(message)
        Translation = namedtuple("Translation", ["lang", "text"])
        return Translation(response.get("lang", "??-??"), response.get("text", [""])[0])
