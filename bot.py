import discord
import json
import subprocess
import sys

from services.command_service import CommandService
from services.command_service.register_commands import register_commands
from services.music_service import MusicService

with open("config.json") as f:
    config = json.load(f)

token = config["secrets"]["discordToken"]


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initialize_services()

    def initialize_services(self):
        self.music_service = MusicService(self)
        self.command_service = CommandService(self)
        register_commands(self)

    async def on_ready(self):
        print("Logged on as", self.user)
        await self.music_service.initialize()

    async def on_message(self, message):
        if message.author == self.user:
            return
        await self.command_service.handle_command(message)

    async def on_voice_state_update(self, member, before, after):
        await self.music_service.handle_voice_state_update(member, before, after)

    async def reset(self):
        subprocess.call(["aws/scripts/application-start.sh"])
        sys.exit(0)


def run_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    client = MyClient(intents=intents)
    client.run(token)


if __name__ == "__main__":
    run_bot()
