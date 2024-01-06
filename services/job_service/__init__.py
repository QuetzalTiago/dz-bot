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

    async def start(self):
        self.is_running = True
        while self.is_running:
            for job in self.jobs:
                if job.last_run is None or time.time() - job.last_run >= job.interval:
                    asyncio.create_task(job.run())
            await asyncio.sleep(1)  # Sleep a bit before checking the jobs again
        print("Job service started.")

    def stop(self):
        self.is_running = False
