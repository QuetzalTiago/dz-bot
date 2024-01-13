from services.file_service import FileService
from services.job_service.job import Job
from services.job_service.job_types import JobType
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

                for song_name in song_names:
                    if song_name not in self.music_service.dl_queue:
                        self.music_service.dl_queue.append(song_name)

                existing_process_db_queue_job = any(
                    map(
                        lambda job: job.job_type == JobType.PROCESS_DB_QUEUE,
                        self.client.job_service.jobs,
                    )
                )

                if not existing_process_db_queue_job:
                    # create job
                    process_dl_queue_job = Job(
                        lambda: self.client.music_service.process_dl_queue(
                            self.message
                        ),
                        10,
                        JobType.PROCESS_DB_QUEUE,
                        5400,  # 90 minutes
                    )

                    await process_dl_queue_job.run()

                    self.client.job_service.add_job(process_dl_queue_job)

            else:
                spotify_name = await self.file_service.get_spotify_name(song_name)
                path, info = await self.file_service.download_from_youtube(
                    spotify_name, self.message
                )
                await self.music_service.add_to_queue(path, info, self.message)

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
            await self.music_service.add_to_queue(path, info, self.message)

        await self.message.clear_reactions()
        await self.message.add_reaction("✅")
