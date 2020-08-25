from leveler.abc import CompositeMetaClass

from .badge import Badge
from .levelup import Levelup
from .profile import Profile
from .rank import Rank


class LevelSet(Badge, Levelup, Profile, Rank, metaclass=CompositeMetaClass):
    """Leveler user settings commands"""
