from services.music_service import MusicService
from ..base import BaseCommand


class SkipCommand(BaseCommand):
    def __init__(self, client, message, music_service: MusicService):
        super().__init__(client, message)
        self.music_service = music_service

    @staticmethod
    def __str__():
        return "Skips the current song."

    async def execute(self):
        await self.music_service.skip_song()
