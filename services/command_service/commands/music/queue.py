from services.music_service import MusicService
from ..base import BaseCommand


class QueueCommand(BaseCommand):
    def __init__(self, client, message, music_service: MusicService):
        super().__init__(client, message)
        self.music_service = music_service

    @staticmethod
    def __str__():
        return "Displays the current queue of songs."

    async def execute(self):
        queue_info_embed = self.music_service.get_queue_info_embed()

        await self.message.channel.send(embed=queue_info_embed)
