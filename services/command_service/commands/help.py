from services.command_service import CommandService
from .base import BaseCommand


class HelpCommand(BaseCommand):
    def __init__(self, client, message, command_service: CommandService):
        super().__init__(client, message)
        self.command_service = command_service

    @staticmethod
    def __str__():
        return "Prints all the available commands."

    async def execute(self):
        av_commands = self.command_service.getCommandsInfo()
        await self.message.channel.send(av_commands)
