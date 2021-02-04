from codecs import lookup

from discord.ext.commands.converter import Converter
from discord.ext.commands.errors import BadArgument


class PySupportedEncoding(Converter):
    async def convert(self, ctx, argument):
        try:
            encoding = lookup(argument)
            if not encoding._is_text_encoding:
                raise BadArgument
        except LookupError:
            raise BadArgument
        else:
            return encoding.name
