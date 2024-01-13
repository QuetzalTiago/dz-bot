from enum import Enum, auto


class JobType(Enum):
    PURGE = "PURGE"
    TEST = "TEST"
    UPDATE_DURATION = "UPDATE_DURATION"
    SAVE_MATCH = "SAVE_MATCH"
    MUSIC = "MUSIC"
    PRINT_JOBS = "PRINT_JOBS"
    PROCESS_DB_QUEUE = "PROCESS_DB_QUEUE"
