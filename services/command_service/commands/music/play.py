import asyncio
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
            if "/playlist/" in song_name:
                song_names = await self.file_service.get_spotify_playlist_songs(
                    song_name
                )
                await self.play_songs_from_list(song_names)
            else:
                spotify_name = await self.file_service.get_spotify_name(song_name)
                path, info = await self.file_service.download_from_youtube(
                    spotify_name, self.message
                )
                await self.play_song(path, info)

        elif "list=" in song_name:  # YouTube playlist
            await self.message.clear_reactions()
            await self.message.add_reaction("❌")
            await self.message.channel.send(
                "Youtube playlists not yet supported. Try a spotify link instead."
            )
            return
            # song_names = await self.file_service.get_youtube_playlist_songs(song_name)
            # await self.play_songs_from_list(song_names)

        else:
            path, info = await self.file_service.download_from_youtube(
                song_name, self.message
            )
            await self.play_song(path, info)

        await self.message.clear_reactions()
        await self.message.add_reaction("✅")

    async def play_song(self, path, info):
        if not self.music_service.is_playing():
            await self.music_service.join_voice_channel(self.message)
        await self.music_service.add_to_queue(path, info, self.message)

    async def play_songs_from_list(self, song_names):
        for next_song_name in song_names:
            (
                next_song_path,
                next_song_info,
            ) = await self.file_service.download_from_youtube(
                next_song_name, self.message
            )

            await self.play_song(next_song_path, next_song_info)

            await asyncio.sleep(5)

        await self.message.clear_reactions()
        await self.message.add_reaction("✅")
