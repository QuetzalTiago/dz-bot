from services.file_service import FileService
from services.music_service import MusicService
from ..base import BaseCommand


class PlayCommand(BaseCommand):
    def __init__(self, client, message, music_service: MusicService):
        super().__init__(client, message)
        self.music_service = music_service
        self.file_service = FileService()

    @staticmethod
    def __str__():
        return "Searches for the song on YouTube and plays it in the current voice channel."

    async def execute(self):
        if self.message.content.startswith("play"):
            song_name = self.message.content[5:].strip()
        else:
            song_name = self.message.content[2:].strip()

        await self.message.add_reaction("⌛")

        if "spotify.com" in song_name:
            path, info = await self.file_service.download_from_spotify(
                song_name, self.message
            )
        else:
            path, info = await self.file_service.download_from_youtube(
                song_name, self.message
            )

        if path and info:
            await self.music_service.join_voice_channel(self.message)
            await self.music_service.add_to_queue(path, info, self.message)
            await self.message.clear_reactions()
            await self.message.add_reaction("✅")
