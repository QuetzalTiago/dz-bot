from services.file_service import FileService
from services.music_service import MusicService
from ..base import BaseCommand


class LoopCommand(BaseCommand):
    def __init__(self, client, message, music_service: MusicService):
        super().__init__(client, message)
        self.music_service = music_service

    @staticmethod
    def __str__():
        return "Toggles loop"

    async def execute(self):
        loop_state = await self.music_service.toggle_loop()
        await self.message.channel.send(f"Loop is now **{loop_state}**.")
