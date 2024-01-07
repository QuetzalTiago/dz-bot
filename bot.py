import datetime
import random
import discord
import json
import subprocess

from services.command_service import CommandService
from services.command_service.register_commands import register_commands
from services.db_service.db_service import DatabaseService

# from services.db_service.db_service import DatabaseService
from services.job_service import JobService
from services.job_service.register_jobs import register_jobs
from services.music_service import MusicService

with open("config.json") as f:
    config = json.load(f)

token = config["secrets"]["discordToken"]
db_url = "mysql+pymysql://root:root@localhost"


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.online_users = {}
        self.main_channel = None
        self.dj_khaled_quotes = [
            "Another one.",
            "We the best.",
            "Major key.",
            "They don't want us to win.",
            "Bless up.",
            "Call me asparagus!",
        ]

    async def initialize_services(self):
        self.command_service = CommandService(self)
        self.music_service = MusicService(self)
        self.job_service = JobService()
        self.db_service = DatabaseService(db_url)

        register_commands(self)
        register_jobs(self)

        await self.music_service.initialize()
        await self.db_service.async_initialize()

        # Should always be the last one
        await self.job_service.initialize()

    async def on_ready(self):
        print("Logged on as", self.user)
        await self.set_first_text_channel_as_main()
        quote = random.choice(self.dj_khaled_quotes)
        await self.main_channel.send(f"**{quote}**")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing, name="another one"
            )
        )

        await self.initialize_services()

    async def on_message(self, message):
        if message.author == self.user:
            return
        await self.command_service.handle_command(message)

    async def on_voice_state_update(self, member, before, after):
        if before.channel and not after.channel:  # User has disconnected
            user_id = member.id
            if user_id in self.online_users:  # Check if the user was tracked
                join_time = self.online_users[user_id]
                leave_time = datetime.datetime.utcnow()
                duration = leave_time - join_time  # Calculate the duration

                # Call a method to handle database update
                self.db_service.update_user_duration(
                    user_id, int(duration.total_seconds())
                )

                del self.online_users[user_id]  # Remove the user from tracking

        elif not before.channel and after.channel:  # User has connected
            # Record the current time and user's id
            self.online_users[member.id] = datetime.datetime.utcnow()
            print(f"Tracking {member.name}")
        await self.music_service.handle_voice_state_update(member, before, after)

    async def set_first_text_channel_as_main(self):
        for guild in self.guilds:
            text_channels = [channel for channel in guild.text_channels]
            text_channels.sort(key=lambda x: x.position)
            if text_channels:
                self.main_channel = text_channels[0]
                print(f"Main channel set to: {self.main_channel.name}")
                break

    async def reset(self):
        subprocess.call(["aws/scripts/application-start.sh"])
        await self.close()


def run_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    client = MyClient(intents=intents)
    client.run(token)


if __name__ == "__main__":
    run_bot()
