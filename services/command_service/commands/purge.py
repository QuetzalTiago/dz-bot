from services.command_service import CommandService
from .base import BaseCommand


class PurgeCommand(BaseCommand):
    def __init__(self, client, message, command_service: CommandService):
        super().__init__(client, message)
        self.command_service = command_service

    @staticmethod
    def __str__():
        return "Purges bot messages and command queries in the current channel."

    async def execute(self):
        await self.message.add_reaction("⌛")
        await self.command_service.purgeMessages(self.message.channel)
