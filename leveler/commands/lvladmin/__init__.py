from leveler.abc import CompositeMetaClass

from .backgrounds import Backgrounds
from .economy import Economy
from .roles import Roles
from .settings import Settings
from .users import Users


class LevelAdmin(Backgrounds, Economy, Roles, Settings, Users, metaclass=CompositeMetaClass):
    """Database converters commands"""
