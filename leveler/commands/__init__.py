from ..abc import CompositeMetaClass
from .database import DataBase
from .db_converters import DBConverters
from .lvladmin import LevelAdmin
from .lvlset import LevelSet
from .other import Other
from .profiles import Profiles
from .top import Top


class LevelerCommands(
    Profiles,
    DataBase,
    Top,
    LevelAdmin,
    LevelSet,
    DBConverters,
    Other,
    metaclass=CompositeMetaClass,
):
    """Class joining all command subclasses"""
