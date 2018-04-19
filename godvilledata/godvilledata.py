import aiohttp
from discord.ext import commands

from cogs.utils import chat_formatting as chat


class GodvilleData:
    """Get data about Godville profiles"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.baseAPI = "https://godville.net/gods/api/"
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def __unload(self):
        self.session.close()

    @commands.command()
    async def godville(self, *, godname: str):
        """Get data about godville's god by name"""
        profile_replacements = {
            "ark_f": "Число собранных тварей женского пола",
            "ark_m": "Число собранных тварей мужского пола",
            "savings": "Примерное число сбережений",
            "t_level": "Уровень героя-торговца",
            "arena_won": "Побед на арене",
            "arena_lost": "Поражений на арене",
            "ark_completed_at": "Дата постройки ковчега",
            "alignment": "Характер героя",
            "bricks_cnt": "Количество кирпичей (шт.)",
            "clan": "Гильдия",
            "clan_position": "Звание в гильдии",
            "gender": "Пол героя",
            # "godname": "Имя бога",
            "inventory_max_num": "В инвентарь помещается",
            "level": "Уровень героя",
            "max_health": "Максимальный запас здоровья",
            # "motto": "Девиз",
            # "name": "Имя героя",
            "savings_completed_at": "Дата окончания сбора пенсии",
            "temple_completed_at": "Дата окончания храма",
            "wood_cnt": "Поленьев",
            "gold_approx": "Золота примерно"
        }
        pet_replacements = {
            "pet_class": "Вид питомца",
            "pet_level": "Уровень питомца",
            "pet_name": "Имя",
            "wounded": "Контужен"
        }
        async with self.session.get("{}/{}".format(self.baseAPI, godname)) as sg:
            if sg.status == 404:
                await self.bot.say(chat.error("404 — Sorry, but there is nothing here\nCheck god name and try again"))
                return
            elif sg.status != 200:
                await self.bot.say(chat.error("Something went wrong. Server returned {}.".format(sg.status)))
            profile = await sg.json()
        god = profile["godname"]
        hero = profile["name"]
        motto = profile["motto"]
        del profile["godname"]
        del profile["name"]
        del profile["motto"]
        del profile["inventory"]  # Deprecated, but still exists, what?
        profile = {k: v for k, v in profile.items() if v is not None}
        text_header = "**{}** и его **{}**\n*{}*\n".format(god, hero, motto)
        text = ""
        for key, value in profile.items():
            if key != "pet":
                text += "{}: {}\n".format(profile_replacements[key], value)
            elif key == "pet":
                text += "Питомец:\n"
                for key, value in profile["pet"].items():
                    text += "    {}: {}\n".format(pet_replacements[key], value)
        await self.bot.say(text_header + chat.box(text))


def setup(bot):
    bot.add_cog(Godville(bot))
