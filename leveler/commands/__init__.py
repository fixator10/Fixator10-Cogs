from ..abc import CompositeMetaClass
from .database import DataBase
from .db_converters import DBConverters
from .lvladmin import LevelAdmin
from .profiles import Profiles
from .top import Top


class LevelerCommands(
    Profiles, DataBase, Top, LevelAdmin, DBConverters, metaclass=CompositeMetaClass
):
    """Class joining all command subclasses"""
