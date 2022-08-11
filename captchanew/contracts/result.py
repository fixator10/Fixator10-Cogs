from typing import TypedDict

import discord

from captchanew.const import State


class ResultContract(TypedDict):
    member: discord.Member
    state: State

    code: str
    attempted_tried: int
