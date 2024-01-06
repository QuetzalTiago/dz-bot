import asyncio
import time
from services.job_service.job import Job


class JobService:
    def __init__(
        self,
    ):
        self.jobs = []
        self.is_running = False

    def add_job(self, job: Job):
        self.jobs.append(job)

    async def initialize(self):
        print("Job service initialized.")
        self.is_running = True
        while self.is_running:
            for job in self.jobs:
                if job.last_run is None or time.time() - job.last_run >= job.interval:
                    asyncio.create_task(job.run())
            await asyncio.sleep(1)  # Sleep a bit before checking the jobs again

    def stop(self):
        self.is_running = False
