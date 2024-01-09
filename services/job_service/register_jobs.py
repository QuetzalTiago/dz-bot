from discord import Client
from services.command_service import CommandService
from services.job_service import JobService
from services.job_service.job import Job
from services.job_service.job_types import JobType


def register_jobs(client: Client):
    job_service: JobService = client.job_service
    command_service: CommandService = client.command_service

    # # Test job
    # Pass a lambda or a reference to an async function. For example:
    # test_job = Job(
    #     lambda: client.main_channel.send(
    #         "This is a test job."
    #     ),  # Lambda
    #     10,  # Interval
    #     JobType.TEST,
    # )
    #
    # Add it to the job service. For example:
    # job_service.add_job(test_job)

    # Purge job
    purge_job = Job(
        lambda: command_service.purgeMessages(client.main_channel),
        1800,
        JobType.PURGE,
    )

    # Notify purge job
    notify_purge_job = Job(
        lambda: client.main_channel.send("Purging messages shortly...⌛"),
        1740,
        JobType.PURGE,
    )

    job_service.add_job(purge_job)
    job_service.add_job(notify_purge_job)
