import datetime
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

    # User Duration Job
    async def update_user_durations():
        for user_id in client.online_users.keys():
            join_time = client.online_users[user_id]
            leave_time = datetime.datetime.utcnow()
            duration = leave_time - join_time

            client.db_service.update_user_duration(
                user_id, int(duration.total_seconds())
            )
        await client.update_online_users()

    user_duration_job = Job(
        update_user_durations,
        60,
        JobType.UPDATE_DURATION,
    )

    job_service.add_job(user_duration_job)
    job_service.add_job(purge_job)
    job_service.add_job(notify_purge_job)
