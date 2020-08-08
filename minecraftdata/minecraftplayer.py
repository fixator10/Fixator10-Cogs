from uuid import UUID

from aiohttp import ClientResponseError, ContentTypeError
from redbot.core.commands import BadArgument
from redbot.core.i18n import Translator

_ = Translator("MinecraftData", __file__)


class MCPlayer:
    def __init__(self, name, uuid):
        self.name = name
        self.uuid = uuid
        self.dashed_uuid = str(UUID(self.uuid))

    def __str__(self):
        return self.name

    @classmethod
    async def convert(cls, ctx, argument):
        try:
            async with ctx.cog.session.get(
                f"https://api.mojang.com/users/profiles/minecraft/{argument}",
                raise_for_status=True,
            ) as data:
                response_data = await data.json()
        except ContentTypeError:
            response_data = None
        except ClientResponseError as e:
            raise BadArgument(_("Unable to get data from Minecraft API: {}").format(e.message))
        if response_data is None or "id" not in response_data:
            raise BadArgument(_("{} not found on Mojang servers").format(argument))
        uuid = str(response_data["id"])
        name = str(response_data["name"])
        try:
            return cls(name, uuid)
        except ValueError:
            raise BadArgument(_("{} is found, but has incorrect UUID.").format(argument))
