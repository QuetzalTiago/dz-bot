from discord import Message
from services.db_service.db_service import DatabaseService
from services.music_service import MusicService
from .base import BaseCommand


class StatusCommand(BaseCommand):
    def __init__(self, client, message: Message, db_service: DatabaseService):
        super().__init__(client, message)
        self.db_service = db_service

    @staticmethod
    def __str__():
        return "Gets the current status for a user."

    async def execute(self):
        user_hours = self.client.db_service.get_user_hours(self.message.author.id)

        if user_hours < 1:
            await self.message.channel.send(
                f"You have not spent an hour yet on the server. Disconnect to refresh."
            )
        else:
            await self.message.channel.send(
                f"You have spent **{user_hours}** hours in the server since 2024."
            )
        await self.message.clear_reactions()
        await self.message.add_reaction("✅")
