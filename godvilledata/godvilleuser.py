from dateutil.parser import parse


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
        self.arena_is_in_fight = bool(profile.get("arena_fight"))
        self.aura = profile.get("aura")
        self.diary_last = profile.get("diary_last")
        self.distance = profile.get("distance")
        self.experience = profile.get("exp_progress")
        self.need_update = bool(profile.get("expired"))
        self.fight_type = profile.get("fight_type")
        self.godpower = profile.get("godpower")
        self.gold_approximately = self._gold or None
        self.health = profile.get("health")
        self.inventory = profile.get("inventory_num")
        self.quest = profile.get("quest")
        self.quest_progress = profile.get("quest_progress")
        self.town = self._town or None

        self.ark_female = profile.get("ark_f")
        self.ark_male = profile.get("ark_m")
        self.savings = profile.get("savings")
        self.trading_level = profile.get("t_level")
        self.arena_won = profile.get("arena_won", 0)
        self.arena_lost = profile.get("arena_lost", 0)
        self.ark_date = profile.get("ark_completed_at")
        self.alignment = profile.get("alignment")
        self.bricks = profile.get("bricks_cnt", 0)
        self.clan = self._clan or None
        self.clan_position = self._clan_pos or None
        self.gender = profile.get("gender")
        self.god = profile.get("godname")
        self.inventory_max = profile.get("inventory_max_num")
        self.level = profile.get("level")
        self.health_max = profile.get("max_health")
        self.motto = self._motto or None
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
            "dungeon": "Подземелье",
        }
        return fights.get(self.fight_type)

    def date_string(self, date: str):
        """Get a date string"""
        dates = {
            "ark": self.ark_date,
            "savings": self.savings_date,
            "temple": self.temple_date,
        }
        if date not in dates:
            raise KeyError
        utctime = (
            parse(dates[date]) - parse(dates[date]).utcoffset()
        )  # shit way to get UTC time out of ISO timestamp
        return utctime.strftime("%d.%m.%Y %H:%M:%S")


class GodvillePet:
    def __init__(self, pet: dict):
        self._level = pet.get("pet_level")
        self.name = pet.get("pet_name")
        self.level = self._level or None
        self.type = pet.get("pet_class")
        self.wounded = bool(pet.get("wounded"))
