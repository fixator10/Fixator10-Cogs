import discord
import os
from cogs.utils import checks
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import error
try:
    import cleverbot

    cbio_lib = True
except:
    cbio_lib = False

class CleverBotIO():
    """CleverBot.IO"""

    def __init__(self, bot:discord.Client):
        self.bot = bot
        self.settings = dataIO.load_json("data/cleverbotio/settings.json")
        self.loop = self.bot.loop
        try:
            self.cleverbot = cleverbot.AsyncClient(api_key=self.settings["key"], user_id=self.settings["user"],
                                                   nick=self.bot.user.name)
        except:
            self.cleverbot = None

    @commands.group(no_pm=True, invoke_without_command=True, pass_context=True, aliases=["cbio"])
    async def cleverbotio(self, ctx, *, message):
        """Talk with cleverbot.io"""
        try:
            result = await self.get_response(message)
        except Exception as e:
            await self.bot.say(error("An exception occurred: {}".format(e)))

    @cleverbotio.command()
    @checks.is_owner()
    async def toggle(self):
        """Toggles reply on mention"""
        self.settings["TOGGLE"] = not self.settings["TOGGLE"]
        if self.settings["TOGGLE"]:
            await self.bot.say("I will reply on mention.")
        else:
            await self.bot.say("I won't reply on mention anymore.")
        dataIO.save_json("data/cleverbotio/settings.json", self.settings)

    @cleverbotio.command()
    @checks.is_owner()
    async def apikey(self, user: str, key: str):
        """Sets token to be used with cleverbot.io

        You can get it from http://cleverbot.io
        Use this command in direct message to keep your
        token secret"""
        self.settings["key"] = key
        self.settings["user"] = user
        dataIO.save_json("data/cleverbotio/settings.json", self.settings)
        await self.bot.say("Credentials set.")

    async def get_response(self, text):
        if self.cleverbot is not None:
            return await self.cleverbot.ask(text)
        else:
            return error("Credentials not set. Use `[p]cleverbotio apikey user key`")

    async def on_message(self, message: discord.Message):
        if not self.settings["TOGGLE"] or message.server is None:
            return

        if not self.bot.user_allowed(message):
            return

        author = message.author
        channel = message.channel

        if message.author.id != self.bot.user.id:
            to_strip = "@" + author.server.me.display_name + " "
            text = message.clean_content
            if not text.startswith(to_strip):
                return
            text = text.replace(to_strip, "", 1)
            await self.bot.send_typing(channel)
            try:
                response = await self.get_response(text)
            except Exception as e:
                await self.bot.send_message(channel, "An exception occured: {}".format(e))
            else:
                await self.bot.send_message(channel, response)

def check_folders():
    if not os.path.exists("data/cleverbotio"):
        print("Creating data/cleverbotio folder...")
        os.makedirs("data/cleverbotio")


def check_files():
    f = "data/cleverbotio/settings.json"
    data = {"TOGGLE": True, "user": None, "key": None}
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, data)


def setup(bot:discord.Client):
    check_folders()
    check_files()
    if cbio_lib:
        bot.add_cog(CleverBotIO(bot))
    else:
        raise RuntimeError("You need to run `pip3 install --upgrade git+git://github.com/Eternity71529/cleverbot.git`")
