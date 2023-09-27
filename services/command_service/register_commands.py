from services.command_service.commands.music.play import PlayCommand
from services.command_service.commands.music.stop import StopCommand
from services.command_service.commands.music.skip import SkipCommand
from services.command_service.commands.music.loop import LoopCommand
from services.command_service.commands.music.queue import QueueCommand
from services.command_service.commands.music.clear import ClearCommand

from services.command_service.commands.btc import BtcCommand
from services.command_service.commands.chess import ChessCommand
from services.command_service.commands.emoji import EmojiCommand
from services.command_service.commands.help import HelpCommand
from services.command_service.commands.purge import PurgeCommand
from services.command_service.commands.restart import RestartCommand


def register_commands(client):
    music_service = client.music_service
    command_service = client.command_service

    # Play
    client.command_service.register_command("play", PlayCommand, True, music_service)
    client.command_service.register_command("p ", PlayCommand, True, music_service)

    # Skip
    client.command_service.register_command("skip", SkipCommand, False, music_service)
    client.command_service.register_command("s", SkipCommand, False, music_service)

    # Loop
    client.command_service.register_command("loop", LoopCommand, False, music_service)

    # Stop
    client.command_service.register_command("stop", StopCommand, False, music_service)

    # Clear
    client.command_service.register_command("clear", ClearCommand, False, music_service)

    # Queue
    client.command_service.register_command("queue", QueueCommand, False, music_service)
    client.command_service.register_command("q", QueueCommand, False, music_service)

    # Purge
    client.command_service.register_command(
        "purge", PurgeCommand, False, command_service
    )

    # Restart
    client.command_service.register_command(
        "restart",
        RestartCommand,
        False,
    )

    # Help
    client.command_service.register_command("help", HelpCommand, False, command_service)

    # Btc
    client.command_service.register_command("btc", BtcCommand)

    # Emoji
    client.command_service.register_command("emoji", EmojiCommand, True)

    # Chess
    client.command_service.register_command("chess", ChessCommand, True)

    print("Commands registered.")
