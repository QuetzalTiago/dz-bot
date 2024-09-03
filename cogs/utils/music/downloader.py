from discord.ext import commands, tasks
from concurrent.futures import ThreadPoolExecutor
import logging
import random
from cogs.api.genius import GeniusAPI
from cogs.api.spotify import SpotifyAPI
from cogs.api.youtube import YouTubeAPI
from cogs.utils.music.state_machine import State


class Downloader:
    def __init__(self, music):
        self.music = music
        self.logger = logging.getLogger("discord")
        self.queue = []
        self.queue_cancelled = False

        self.spotify = SpotifyAPI(music.config)
        self.youtube = YouTubeAPI(music.config)
        self.genius = GeniusAPI(music.config)

    def set_queue(self, queue):
        self.queue = queue

        if not len(queue):
            self.logger.info(f"Download queue cleared")
        else:
            self.logger.info(f"Download queue set to: {queue}")

    def set_queue_cancelled(self, value: bool):
        self.logger.info(f"Download queue canceled set to: {value}")
        self.queue_cancelled = value

    @tasks.loop(seconds=30)
    async def process_queue(self):
        if len(self.queue) == 0:
            self.process_queue.stop()
            return

        await self.download_next_song()

    async def get_spotify_songs(self, url, message):
        song_names = []

        if "/playlist/" in url:
            song_names = await self.spotify.get_playlist_songs(url)

        elif "/album/" in url:
            song_names = await self.spotify.get_album_songs(url)
        else:
            spotify_name = await self.spotify.get_track_name(url)
            song_names.append(spotify_name)

        if song_names:
            songs = map((lambda song_name: (song_name, message, True)), song_names)

        return songs

    async def download_next_song(self):
        if len(self.queue) == 0:
            return

        pop_index = 0
        if self.music.playlist.shuffle:
            pop_index = random.randint(0, len(self.queue) - 1)

        next_song_name, message, spotify_req = self.queue.pop(pop_index)

        try:
            await message.add_reaction("⌛")
        except:
            pass

        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                is_playable = await self.music.bot.loop.run_in_executor(
                    executor, self.youtube.is_video_playable, next_song_name
                )
            except:
                is_playable = False

        if not is_playable:
            sent_message = await message.channel.send(
                f"**{next_song_name}** is too long or there was an error downloading the song. Try another query."
            )
            await self.music.cog_failure(sent_message, message)
            return

        lyrics = None
        if spotify_req:
            lyrics = await self.genius.fetch_lyrics(next_song_name)
            next_song_name = f"{next_song_name} audio"

        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                next_song_path, next_song_info = (
                    await self.music.bot.loop.run_in_executor(
                        executor, self.youtube.download, next_song_name
                    )
                )
            except:
                sent_message = await message.channel.send(
                    f"**{next_song_name}** is too long or there was an error downloading the song. Try another query."
                )
                await self.music.cog_failure(sent_message, message)
                return

        # Mark download complete if the song message is not on download queue
        if all(message is not item[1] for item in self.queue):
            await self.music.cog_success(message)

        if self.queue_cancelled:
            self.set_queue_cancelled(False)
            self.process_queue.stop()
            self.music.state_machine.stop()
        else:
            await self.music.playlist.add(
                next_song_path, next_song_info, message, lyrics
            )

        await self.music.playlist.update_message()

    async def enqueue(self, query, message):
        songs = []

        if "spotify.com" in query:
            songs = await self.get_spotify_songs(query, message)
        else:
            songs = [(query, message, False)]

        for song in songs:
            if song not in self.queue:
                combined_total_song_len = len(self.queue) + len(
                    self.music.playlist.songs
                )

                if combined_total_song_len + 1 <= self.music.playlist.max_size:
                    self.queue.append(song)

                    if self.queue_cancelled:
                        self.set_queue_cancelled(False)

        if not self.process_queue.is_running():
            await self.download_next_song()
            self.process_queue.start()

        self.music.state_machine.start()

    async def clear(self):
        self.set_queue([])
        self.set_queue_cancelled(True)
