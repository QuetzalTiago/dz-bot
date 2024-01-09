import time
from typing import Callable
from services.job_service.job_types import JobType


class Job:
    def __init__(
        self,
        coro_func: Callable,
        interval: int,
        job_type: JobType,
    ):
        self.coro_func = coro_func  #  lambda returning a coroutine
        self.interval = interval
        self.job_type = job_type
        self.last_run = None

    async def run(self):
        coroutine = self.coro_func()  # Call the coroutine function without arguments
        await coroutine  # Await the coroutine
        self.last_run = time.time()  # Update last run time
