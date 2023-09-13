import discord
import json

from services.command_service import CommandService
from services.music_service import MusicService

from services.command_service.commands.stop import StopCommand
from services.command_service.commands.btc import BtcCommand
from services.command_service.commands.chess import ChessCommand
from services.command_service.commands.emoji import EmojiCommand
from services.command_service.commands.play import PlayCommand
from services.command_service.commands.skip import SkipCommand
from services.command_service.commands.loop import LoopCommand
from services.command_service.commands.queue import QueueCommand
from services.command_service.commands.help import HelpCommand
from services.command_service.commands.clear import ClearCommand
from services.command_service.commands.purge import PurgeCommand

# Get credentials
with open("config.json") as f:
    config = json.load(f)

# Discord token
token = config["secrets"]["discordToken"]


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.music_service = MusicService(self)
        self.command_service = CommandService(self)

    async def on_ready(self):
        print("Logged on as", self.user)
        self.command_service.register_command("btc", BtcCommand)
        self.command_service.register_command("emoji", EmojiCommand, True)
        self.command_service.register_command("chess", ChessCommand, True)

        self.command_service.register_command(
            "play", PlayCommand, self.music_service, True
        )
        self.command_service.register_command(
            "p ", PlayCommand, self.music_service, True
        )

        self.command_service.register_command("skip", SkipCommand, self.music_service)
        self.command_service.register_command("s", SkipCommand, self.music_service)

        self.command_service.register_command("loop", LoopCommand, self.music_service)
        self.command_service.register_command("stop", StopCommand, self.music_service)
        self.command_service.register_command(
            "purge", PurgeCommand, self.command_service
        )
        self.command_service.register_command("clear", ClearCommand, self.music_service)
        self.command_service.register_command("help", HelpCommand, self.command_service)

        self.command_service.register_command("queue", QueueCommand, self.music_service)
        self.command_service.register_command("q", QueueCommand, self.music_service)

        print("Commands registered.")

    async def on_message(self, message):
        if message.author == self.user:
            return
        await self.command_service.handle_command(message)


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = MyClient(intents=intents)
client.run(token)
