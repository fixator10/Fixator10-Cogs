from leveler.abc import CompositeMetaClass

from .backgrounds import Backgrounds
from .badge import Badge
from .debugging import Debugging
from .economy import Economy
from .roles import Roles
from .settings import Settings
from .users import Users


class LevelAdmin(
    Backgrounds, Economy, Roles, Settings, Users, Badge, Debugging, metaclass=CompositeMetaClass
):
    """Leveler administration commands"""
