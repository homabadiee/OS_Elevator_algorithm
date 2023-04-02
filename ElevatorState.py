from enum import Enum

class ElevatorState(Enum):
    idle = "IDLE"
    going_up = "UP"
    going_down = "DOWN"
    wait = "WAIT"

class Direction(Enum):
    up = 2
    down = 3

