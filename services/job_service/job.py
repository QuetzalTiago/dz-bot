import time
from typing import Callable, Any
from services.job_service.job_types import JobType


class Job:
    def __init__(
        self, coro_func: Callable, args: tuple, interval: int, job_type: JobType
    ):
        self.coro_func = coro_func  # The coroutine function
        self.args = args  # Arguments to pass to the coroutine function
        self.interval = interval
        self.job_type = job_type
        self.last_run = None

    async def run(self):
        # Create a new coroutine object from the coroutine function and arguments
        coroutine = self.coro_func(*self.args)
        await coroutine
        self.last_run = time.time()
