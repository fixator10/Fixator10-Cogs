from enum import Enum
from typing import Dict, Type, Union

import discapty


class State(Enum):
    COMPLETED = "Completed"
    FAILED = "Failed"
    FAILURE = "Internal Failure"


FROM_TYPE_TO_GENERATOR: Dict[str, Type[discapty.Generator]] = {
    "text": discapty.TextGenerator,
    "wheezy": discapty.WheezyGenerator,
    "image": discapty.ImageGenerator,
}
