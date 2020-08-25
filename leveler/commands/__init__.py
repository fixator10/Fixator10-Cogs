from ..abc import CompositeMetaClass
from .profiles import Profiles
from .database import DataBase
from .top import Top
from .db_converters import DBConverters


class LevelerCommands(
    Profiles,
    DataBase,
    Top,
    DBConverters,
    metaclass=CompositeMetaClass
):
    """Class joining all command subclasses"""
