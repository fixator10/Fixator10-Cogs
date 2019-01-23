import os

import aiohttp
from dateutil.parser import parse
from discord.ext import commands

from cogs.utils import chat_formatting as chat
from cogs.utils.dataIO import dataIO


class GodvilleData:
    """Get data about Godville profiles"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.baseAPI = "https://godville.net/gods/api/"
        self.config_file = "data/godville/config.json"
        self.config = dataIO.load_json(self.config_file)
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def __unload(self):
        self.session.close()

    async def api_by_god(self, godname: str):
        """Get apikey by godname
        :param godname: name of god to get key"""
        for user, data in self.config.items():
            if data["godname"] == godname:
                return data["apikey"]
        return None

    @commands.group(invoke_without_command=True)
    @commands.cooldown(30, 10 * 60, commands.BucketType.user)
    async def godville(self, *, godname: str):
        """Get data about godville's god by name"""
        async with self.session.get("{}/{}/{}".format(self.baseAPI,
                                                      godname.casefold(),
                                                      await self.api_by_god(godname.casefold()) or "")) as sg:
            if sg.status == 404:
                await self.bot.say(chat.error("404 — Sorry, but there is nothing here\nCheck god name and try again"))
                return
            elif sg.status != 200:
                await self.bot.say(chat.error("Something went wrong. Server returned {}.".format(sg.status)))
                return
            profile = await sg.json()
        profile = GodvilleUser(profile)
        text_header = "{} и его {}\n{}\n".format(chat.bold(profile.god),
                                                 chat.bold(profile.name),
                                                 chat.italics(chat.escape(profile.motto.strip(), formatting=True)
                                                              if profile.motto else chat.inline("Здесь ничего нет")))
        if profile.arena_is_in_fight:
            text_header += "В сражении: {}\n".format(profile.fight_type_rus)
        if profile.town:
            text_header += "В городе: {}\n".format(profile.town)
        if profile.need_update:
            text_header += chat.bold("! УСТАРЕВШАЯ ИНФОРМАЦИЯ !") + "\n"
        text = ""
        pet = ""
        times = ""
        if profile.gold_approximately:
            text += "Золота: {}\n".format(profile.gold_approximately)
        if profile.distance:
            text += "Столбов от столицы: {}\n".format(profile.distance)
        if profile.quest_progress:
            text += "Задание: {} ({}%)\n".format(profile.quest, profile.quest_progress)
        if profile.experience:
            text += "Опыта до следующего уровня: {}%\n".format(profile.experience)
        text += "Уровень: {}\n".format(profile.level)
        if profile.godpower:
            text += "Праны: {}/{}\n".format(profile.godpower, 200 if profile.savings_date else 100)
        text += "Характер: {}\n".format(profile.alignment)
        text += "Пол: {}\n".format(profile.gender)
        text += "Побед/Поражений: {}/{}\n".format(profile.arena_won, profile.arena_lost)
        text += "Гильдия: {} ({})\n".format(profile.clan, profile.clan_position) if profile.clan \
            else "Гильдия: Не состоит\n"
        text += "Кирпичей: {} ({}%)\n".format(profile.bricks, profile.bricks / 10)
        if profile.inventory:
            text += "Инвентарь: {}/{} ({}%)\n".format(profile.inventory, profile.inventory_max,
                                                      int(profile.inventory / profile.inventory_max * 100))
        else:
            text += "Вместимость инвентаря: {}\n".format(profile.inventory_max)
        if profile.health:
            text += "Здоровье: {}/{} ({}%)\n".format(profile.health, profile.health_max,
                                                     int(profile.health / profile.health_max * 100))
        else:
            text += "Максимум здоровья: {}\n".format(profile.health_max)
        if profile.ark_male:
            text += "Тварей ♂: {} ({}%)\n".format(profile.ark_male, profile.ark_male / 10)
        if profile.ark_female:
            text += "Тварей ♀: {} ({}%)\n".format(profile.ark_female, profile.ark_female / 10)
        if profile.savings:
            text += "Сбережений: {}\n".format(profile.savings)
        if profile.trading_level:
            text += "Уровень торговли: {}\n".format(profile.trading_level)
        if profile.wood:
            text += "Поленьев: {} ({}%)\n".format(profile.wood, profile.wood / 10)

        # private (api only)
        if profile.diary_last:
            text += "Дневник: {}\n".format(profile.diary_last)
        if profile.activatables:
            text += "Активируемое в инвентаре: {}\n".format(", ".join(profile.activatables))
        if profile.aura:
            text += "Аура: {}\n".format(profile.aura)

        # pet
        if profile.pet.name:
            pet += "Имя: {}\n".format(profile.pet.name)
            pet += "Уровень: {}\n".format(profile.pet.level or "Без уровня")
            if profile.pet.type:
                pet += "Тип: {}\n".format(profile.pet.type)
            if profile.pet.wounded:
                pet += "❌ — Контужен"

        # times
        if profile.temple_date:
            times += "Храм достроен: {}\n".format(profile.date_string("temple"))
        if profile.ark_date:
            times += "Ковчег достроен: {}\n".format(profile.date_string("ark"))
        if profile.savings_date:
            times += "Пенсия собрана: {}\n".format(profile.date_string("savings"))

        finaltext = ""
        finaltext += text_header
        finaltext += chat.box(text)
        if pet:
            finaltext += "Питомец:\n"
            finaltext += chat.box(pet)
        if times:
            finaltext += chat.box(times)
        await self.bot.say(finaltext)

    @godville.group(pass_context=True, invoke_without_command=True)
    async def apikey(self, ctx: commands.Context, apikey: str, *, godname: str):
        """Set apikey for your character.
        Only one character per user"""
        self.config[ctx.message.author.id] = {"godname": godname.casefold(),
                                              "apikey": apikey}
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say("Your name and apikey has been saved")

    @apikey.command(pass_context=True)
    async def remove(self, ctx: commands.Context):
        """Remove your apikey and godname from bot's data"""
        del self.config[ctx.message.author.id]
        dataIO.save_json(self.config_file, self.config)
        await self.bot.say("Your key removed from database")


class GodvilleUser(object):
    """Godville API wrapper"""

    def __init__(self, profile: dict):
        self._clan = profile.get("clan")
        self._clan_pos = profile.get("clan_position")
        self._motto = profile.get("motto")
        self._pet_data = profile.get("pet", {})
        self._gold = profile.get("gold_approx")
        self._town = profile.get("town_name")

        self.activatables = profile.get("activatables")
        self.arena_is_in_fight = True if profile.get("arena_fight") else False
        self.aura = profile.get("aura")
        self.diary_last = profile.get("diary_last")
        self.distance = profile.get("distance")
        self.experience = profile.get("exp_progress")
        self.need_update = True if profile.get("expired") else False
        self.fight_type = profile.get("fight_type")
        self.godpower = profile.get("godpower")
        self.gold_approximately = self._gold if self._gold else None
        self.health = profile.get("health")
        self.inventory = profile.get("inventory_num")
        self.quest = profile.get("quest")
        self.quest_progress = profile.get("quest_progress")
        self.town = self._town if self._town else None

        self.ark_female = profile.get("ark_f")
        self.ark_male = profile.get("ark_m")
        self.savings = profile.get("savings")
        self.trading_level = profile.get("t_level")
        self.arena_won = profile.get("arena_won", 0)
        self.arena_lost = profile.get("arena_lost", 0)
        self.ark_date = profile.get("ark_completed_at")
        self.alignment = profile.get("alignment")
        self.bricks = profile.get("bricks_cnt", 0)
        self.clan = self._clan if self._clan else None
        self.clan_position = self._clan_pos if self._clan_pos else None
        self.gender = profile.get("gender")
        self.god = profile.get("godname")
        self.inventory_max = profile.get("inventory_max_num")
        self.level = profile.get("level")
        self.health_max = profile.get("max_health")
        self.motto = self._motto if self._motto else None
        self.name = profile.get("name")
        self.savings_date = profile.get("savings_completed_at")
        self.temple_date = profile.get("temple_completed_at")
        self.wood = profile.get("wood_cnt")

        self.pet = GodvillePet(self._pet_data)

    @property
    def fight_type_rus(self):
        fights = {
            "sail": "Морской поход",
            "arena": "Арена",
            "challenge": "Тренировка",
            "dungeon": "Подземелье"
        }
        return fights.get(self.fight_type)

    def date_string(self, date: str):
        """Get a date string"""
        dates = {
            "ark": self.ark_date,
            "savings": self.savings_date,
            "temple": self.temple_date
        }
        if date not in dates:
            raise KeyError
        utctime = parse(dates[date]) - parse(dates[date]).utcoffset()  # shit way to get UTC time out of ISO timestamp
        return utctime.strftime('%d.%m.%Y %H:%M:%S')


class GodvillePet:
    def __init__(self, pet: dict):
        self._level = pet.get("pet_level")
        self.name = pet.get("pet_name")
        self.level = self._level if self._level else None
        self.type = pet.get("pet_class")
        self.wounded = True if pet.get("wounded") else False


def check_folders():
    if not os.path.exists("data/godville"):
        os.makedirs("data/godville")


def check_files():
    system = {}
    f = "data/godville/config.json"
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, system)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(GodvilleData(bot))
