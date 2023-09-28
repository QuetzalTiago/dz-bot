from services.command_service import CommandService
from .base import BaseCommand


class RestartCommand(BaseCommand):
    def __init__(self, client, message):
        super().__init__(client, message)

    @staticmethod
    def __str__():
        return "Restarts the bot and resets its state."

    async def execute(self):
        await self.message.add_reaction("🔄")
        await self.client.reset()
