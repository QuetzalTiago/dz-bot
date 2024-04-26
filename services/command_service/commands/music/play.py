from services.file_service import FileService
from services.job_service.job import Job
from services.job_service.job_types import JobType
from services.music_service import MusicService
from ..base import BaseCommand


class PlayCommand(BaseCommand):
    def __init__(self, client, message):
        super().__init__(client, message)

    @staticmethod
    def __str__():
        return "Searches for the song on YouTube and plays it in the current voice channel."

    async def handle_spotify_url(self, url):
        song_names = []

        if "/playlist/" in url:
            song_names = await self.client.music_service.get_spotify_playlist_songs(url)
        elif "/album/" in url:
            song_names = await self.client.music_service.get_spotify_album_songs(url)
        else:
            spotify_name = await self.client.music_service.get_spotify_name(url)
            path, info = await self.client.file_service.download_from_youtube(
                spotify_name, self.message
            )
            await self.client.music_service.add_to_queue(path, info, self.message)
            return

        if song_names:
            await self.client.music_service.enqueue_songs(song_names, self.message)

    async def execute(self):
        if self.message.author.voice is None:
            await self.message.channel.send("You are not connected to a voice channel!")
            await self.message.clear_reactions()
            await self.message.add_reaction("❌")
            return

        if self.message.content.startswith("play"):
            song_name = self.message.content[5:].strip()
        else:
            song_name = self.message.content[2:].strip()

        await self.message.add_reaction("⌛")

        if "spotify.com" in song_name:
            await self.handle_spotify_url(song_name)
            return

        elif "list=" in song_name:  # YouTube playlist
            await self.message.clear_reactions()
            await self.message.add_reaction("❌")
            await self.message.channel.send(
                "Youtube playlists not yet supported. Try a spotify link instead."
            )
            return
            # song_names = await self.client.music_service.get_youtube_playlist_songs(song_name)
            # await self.play_songs_from_list(song_names)

        else:
            await self.client.music_service.enqueue_songs([song_name], self.message)

        await self.message.clear_reactions()
        await self.message.add_reaction("✅")
