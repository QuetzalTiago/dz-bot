import datetime
import random
import discord
import json
import subprocess

from services.command_service import CommandService
from services.command_service.register_commands import register_commands
from services.db_service.db_service import DatabaseService
from services.file_service import FileService
from services.job_service import JobService
from services.job_service.register_jobs import register_jobs
from services.music_service import MusicService

with open("config.json") as f:
    config = json.load(f)

token = config["secrets"]["discordToken"]
db_url = "mysql+pymysql://root:root@localhost"


class Khaled(discord.Client):
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
        self.max_duration = 1200  # in seconds, 20 minutes

    async def initialize_services(self):
        self.command_service = CommandService(self)
        self.music_service = MusicService(self)
        self.db_service = DatabaseService(db_url)
        self.job_service = JobService(self)
        self.file_service = FileService(self)

        # Commands
        register_commands(self)

        # Music
        await self.music_service.initialize()

        # Database
        await self.db_service.async_initialize()

        # Register jobs (should be after db init)
        await register_jobs(self)

        # Job service (should always be the last one)
        await self.job_service.initialize()

    async def on_ready(self):
        print("Logged on as", self.user)
        await self.set_first_text_channel_as_main()
        quote = random.choice(self.dj_khaled_quotes)
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.custom, name=quote)
        )

        await self.initialize_services()
        await self.update_online_users()
        # Notify after reset
        message_id, channel_id = self.db_service.get_startup_notification()
        if message_id and channel_id:
            message = await self.fetch_message_by_id(channel_id, message_id)
            if message:
                await message.clear_reactions()
                await message.add_reaction("✅")

                # Reset the notify_on_startup flag in the database
                self.db_service.set_startup_notification(None, None)

    async def on_message(self, message):
        if message.author == self.user:
            return
        await self.command_service.handle_command(message)

    async def update_online_users(self):
        for guild in self.guilds:
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if not member.bot:
                        self.online_users[member.id] = datetime.datetime.utcnow()
                        print(f"Tracking already connected user: {member.name}")

    async def on_voice_state_update(self, member, before, after):
        if before.channel and not after.channel:  # User has disconnected
            user_id = member.id
            if user_id in self.online_users:  # Check if the user was tracked
                del self.online_users[user_id]  # Remove the user from tracking

        elif not before.channel and after.channel:  # User has connected
            self.online_users[member.id] = datetime.datetime.utcnow()
            print(f"Tracking {member.name}")

        if member == self.user and after is None:
            await self.music_service.stop()

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

    async def fetch_message_by_id(self, channel_id, message_id):
        try:
            # Convert the IDs to integers
            channel_id = int(channel_id)
            message_id = int(message_id)
        except ValueError:
            print("Invalid channel or message ID. IDs must be integers.")
            return None

        channel = self.get_channel(channel_id)
        if channel:
            try:
                message = await channel.fetch_message(message_id)
                return message
            except Exception as e:
                print(f"Failed to fetch message: {e}")
        else:
            print(f"Channel with ID {channel_id} not found.")
            return None


def run_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    client = Khaled(intents=intents)
    client.run(token)


if __name__ == "__main__":
    run_bot()
