# I REALIZE TODAY THAT PYTHON'S EXCEPTIONS ARE AWESOME!


from typing import Any, List, Optional, Union


class MissingRequiredSettingError(Exception):
    setting: str
    actual_value: Union[Any, None]

    def __init__(self, setting: str, value: Union[Any, None]) -> None:
        self.setting = setting
        self.actual_value = value


class MissingRequiredPermissionsError(Exception):
    permissions: List[str]
    in_destination: Optional[str]

    def __init__(self, permissions: List[str], in_destination: Optional[str] = None) -> None:
        self.permissions = permissions
        self.in_destination = in_destination
