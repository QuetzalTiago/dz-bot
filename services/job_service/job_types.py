from enum import Enum, auto


class JobType(Enum):
    PURGE = auto()
    TEST = auto()
    UPDATE_DURATION = auto()


# You might add more job types as needed, like:
# CLEANUP = auto()
# BACKUP = auto()
# NOTIFY = auto()
