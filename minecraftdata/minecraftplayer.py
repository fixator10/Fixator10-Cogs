from uuid import UUID

from aiohttp import ContentTypeError
from redbot.core.commands import BadArgument
from redbot.core.i18n import Translator

_ = Translator("MinecraftData", __file__)


class MCPlayer:
    def __init__(self, nickname, uuid):
        self.name = nickname
        self.uuid = uuid
        self.dashed_uuid = str(UUID(hex=uuid))

    @classmethod
    async def convert(cls, ctx, argument):
        try:
            async with ctx.cog.session.get(
                f"https://api.mojang.com/users/profiles/minecraft/{argument}"
            ) as data:
                response_data = await data.json()
        except ContentTypeError:
            response_data = None
        except Exception as e:
            raise BadArgument(_("Unable to get data from Minecraft API: {}").format(e))
        if response_data is None or "id" not in response_data:
            raise BadArgument(_("{} not found on Mojang servers").format(argument))
        uuid = str(response_data["id"])
        name = str(response_data["name"])
        return cls(name, uuid)
