from discord import Client
from services.command_service import CommandService
from services.job_service import JobService
from services.job_service.job import Job
from services.job_service.job_types import JobType


def register_jobs(client: Client):
    job_serv: JobService = client.job_service
    command_service: CommandService = client.command_service

    # Purge
    purge_job = Job(
        command_service.purgeMessages,  # The coroutine function
        (client.main_channel,),  # The arguments as a tuple
        1800,  # Interval
        JobType.PURGE,
    )

    # Notify purge
    purge_job = Job(
        client.main_channel.send("Purging server in one minute...⌛"),
        (client.main_channel,),
        1740,
        JobType.PURGE,
    )
    job_serv.add_job(purge_job)
