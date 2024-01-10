import time
from typing import Callable
from services.job_service.job_types import JobType


class Job:
    def __init__(
        self, coro_func: Callable, interval: int, job_type: JobType, is_periodic=True
    ):
        self.coro_func = coro_func  #  lambda returning a coroutine
        self.interval = interval
        self.job_type = job_type
        self.last_run = None
        self.is_periodic = is_periodic

    async def run(self):
        coroutine = self.coro_func()  # Call the coroutine function without arguments
        await coroutine  # Await the coroutine
        self.last_run = time.time()  # Update last run time
