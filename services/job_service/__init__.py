import asyncio
import time
from services.job_service.job import Job


class JobService:
    def __init__(self, client):
        self.client = client
        self.jobs = []

    def add_job(self, job: Job):
        self.jobs.append(job)

    async def print_jobs(self):
        print("-------------------------")
        print("RUNNING JOBS:")
        for job in self.jobs:
            print(job.job_type)
        print("-------------------------")
        print("")

    def remove_job(self, job_type):
        for job in self.jobs:
            if job.job_type == job_type:
                self.jobs.remove(job)
                break

    async def initialize(self):
        self.client.loop.create_task(self.background_task())
        print("Job service initialized.")

    async def background_task(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            current_time = time.time()
            for job in self.jobs:
                # If the job never ran, set the last_run to the current time
                if job.last_run is None:
                    job.last_run = current_time

                # Check if the job should run based on the interval
                if current_time - job.last_run >= job.interval:
                    asyncio.create_task(job.run())

                    if not job.is_periodic:
                        self.jobs.remove(job)

            await asyncio.sleep(1)  # Sleep a bit before checking the jobs again
