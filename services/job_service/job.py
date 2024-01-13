import time
from typing import Callable
from services.job_service.job_types import JobType


class Job:
    def __init__(
        self,
        coro_func: Callable,
        interval: int,
        job_type: JobType,
        timeout=None,
        is_periodic=True,
    ):
        self.coro_func = coro_func  # lambda returning a coroutine
        self.interval = interval
        self.job_type = job_type
        self.last_run = None
        self.is_periodic = is_periodic
        self.timeout = timeout
        self.start_time = None

    async def run(self):
        current_time = time.time()

        self.last_run = current_time
        self.start_time = current_time

        coroutine = self.coro_func()  # Call the coroutine function without arguments
        await coroutine  # Await the coroutine
