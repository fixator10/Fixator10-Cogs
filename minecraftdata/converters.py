from uuid import UUID

from redbot.core.commands import BadArgument
from redbot.core.commands import Converter


class MCUUID:
    def __init__(self, nickname, uuid):
        self.name = nickname
        self.uuid = uuid
        self.dashed_uuid = str(UUID(hex=uuid))


class MCNickname(Converter):
    async def convert(self, ctx, argument):
        session = ctx.cog.session
        try:
            async with session.get('https://api.mojang.com/users/profiles/minecraft/' + argument) as data:
                response_data = await data.json()
        except:
            raise BadArgument("Unable to get data from Minecraft API")
        if response_data is None or "id" not in response_data:
            raise BadArgument("{} not found on Mojang servers".format(argument))
        uuid = str(response_data["id"])
        name = str(response_data["name"])
        return MCUUID(name, uuid)
