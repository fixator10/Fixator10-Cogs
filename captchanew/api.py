import discapty
import discord

from .abc import CogABC
from .config import GuildSettings
from .const import FROM_TYPE_TO_GENERATOR


class CaptchaAPI(CogABC):
    def should_accept_challenge(self, guild: discord.Guild) -> bool:
        guild_queue = self.queue.get(guild.id)
        return len(guild_queue) < 5 if guild_queue else True

    async def start_challenge_for_member(self, member: discord.Member) -> discapty.Challenge:
        guild = member.guild
        config = await GuildSettings.from_guild(guild)
        generator = FROM_TYPE_TO_GENERATOR[config.type]()

        # TODO: Remove type: ignore at d.py 2.0
        challenge = discapty.Challenge(generator, f"{guild.id}-{member.id}", allowed_retries=config.retries)  # type: ignore
        self.queue
