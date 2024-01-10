from enum import Enum, auto


class JobType(Enum):
    PURGE = "PURGE"
    TEST = "TEST"
    UPDATE_DURATION = "UPDATE_DURATION"
    SAVE_MATCH = "SAVE_MATCH"
