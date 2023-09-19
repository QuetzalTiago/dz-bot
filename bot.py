import discord
import json

from services.command_service import CommandService
from services.command_service.register_commands import register_commands
from services.music_service import MusicService

with open("config.json") as f:
    config = json.load(f)

token = config["secrets"]["discordToken"]


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.music_service = MusicService(self)
        self.command_service = CommandService(self)

    async def on_ready(self):
        print("Logged on as", self.user)
        register_commands(self)
        await self.music_service.initialize()

    async def on_message(self, message):
        if message.author == self.user:
            return
        await self.command_service.handle_command(message)

    async def on_voice_state_update(self, member, before, after):
        if member == self.user and before.channel is not None and after.channel is None:
            # The bot was in a voice channel before but is no longer in one now.
            print("Bot was removed from a voice channel.")
            await self.music_service.cleanup()  # Assuming your MusicService has a cleanup method


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = MyClient(intents=intents)
client.run(token)
