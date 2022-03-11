import argparse
from shlex import split

from redbot.core import commands


class NoExitParser(argparse.ArgumentParser):
    def error(self, message):
        raise commands.BadArgument(message)


class TopParser(commands.Converter):
    page: int
    global_top: bool
    rep: bool
    server: str

    async def convert(self, ctx, argument):
        parser = NoExitParser(description="top command arguments parser", add_help=False)
        parser.add_argument("page", nargs="?", type=int, default="1")
        parser.add_argument("-g", "--global", dest="global_top", action="store_true")
        parser.add_argument("-r", "--rep", action="store_true")
        parser.add_argument("-s", "--server", "--guild", type=str, nargs="*")
        try:
            return parser.parse_args(split(argument))
        except ValueError as e:
            raise commands.BadArgument(*e.args)
