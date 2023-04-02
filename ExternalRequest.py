from enum import Enum

class ExternalRequestState(Enum):
    unassigned = "UNASSIGNED"
    waiting = "WAITING"
    finished = "FINISHED"


class ExternalRequest:
    def __init__(self, target, move_direction, state=ExternalRequestState.unassigned):  # the task is unfinished by default
        self.target = target
        self.move_direction = move_direction  # Required direction of elevator travel
        self.state = state