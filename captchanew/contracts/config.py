from typing import List, Literal, Optional, TypedDict, Union


class GuildConfigContract(TypedDict):
    channel: Union[int, Literal["dm"], None]
    logs_channel: Optional[int]
    enabled: bool
    auto_roles: List[int]
    temp_role: Optional[int]
    type: Literal["text", "wheezy", "image"]
    timeout: int
    retries: int
    simultaneous_challenges: int
