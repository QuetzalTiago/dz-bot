import datetime
import requests
from discord import Client
from services.command_service import CommandService
from services.job_service import JobService
from services.job_service.job import Job
from services.job_service.job_types import JobType


async def register_jobs(client: Client):
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
        7200,  # 2 hours
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
        30,
        JobType.UPDATE_DURATION,
    )

    # Print running jobs
    print_running_jobs_job = Job(client.job_service.print_jobs, 30, JobType.PRINT_JOBS)

    async def check_and_notify_bitcoin_price_change():
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        data = response.json()
        current_price = float(data["data"]["amount"])

        last_price = client.db_service.get_bitcoin_price()

        threshold = 0.025  # 2.5% change threshold

        if last_price is not None:
            price_change = current_price - last_price
            percentage_change = (price_change / last_price) * 100

            if abs(percentage_change) >= threshold * 100:
                formatted_current_price = format(int(current_price), ",d")
                formatted_price_change = format(int(abs(price_change)), ",d")

                change_direction = "increased" if price_change > 0 else "decreased"
                notification_message = (
                    f"Bitcoin price has {change_direction} to **{formatted_current_price} USD** "
                    f"({formatted_price_change} USD, {abs(percentage_change):.2f}% change)."
                )

                await client.main_channel.send(notification_message)

        client.db_service.update_bitcoin_price(current_price)

    btc_price_check_job = Job(
        check_and_notify_bitcoin_price_change,
        3600,  # Check every hour
        JobType.CHECK_BTC_CHANGE,
    )

    try:
        await btc_price_check_job.run()
    except Exception as e:
        print(e)

    job_service.add_job(btc_price_check_job)
    job_service.add_job(user_duration_job)
    job_service.add_job(purge_job)
    job_service.add_job(print_running_jobs_job)
