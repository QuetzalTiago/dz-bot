import logging
import random
from concurrent.futures import ThreadPoolExecutor

from discord.ext import tasks

from cogs.api.genius import GeniusAPI
from cogs.api.spotify import SpotifyAPI
from cogs.api.youtube import YouTubeAPI
from cogs.utils.emojis import PROCESSING
from cogs.utils.music.state_machine import State


class Downloader:
    def __init__(self, state):
        # `state` is the per-guild GuildMusicState.
        self.state = state
        self.logger = logging.getLogger("discord")
        self.queue = []
        self.queue_cancelled = False
        # A single shared executor rather than one per download.
        self.executor = ThreadPoolExecutor(max_workers=1)

        self.spotify = SpotifyAPI(state.config)
        self.youtube = YouTubeAPI(state.config)
        self.genius = GeniusAPI(state.config)

    def set_queue(self, queue):
        self.queue = queue

    def set_queue_cancelled(self, value: bool):
        self.queue_cancelled = value

    @tasks.loop(seconds=30)
    async def process_queue(self):
        try:
            if len(self.queue) == 0:
                self.process_queue.stop()
                return
            await self.download_next_song()
        except Exception:
            self.logger.exception("Error processing download queue")

    async def get_spotify_songs(self, url, message):
        song_names = []
        if "/playlist/" in url:
            song_names = await self.spotify.get_playlist_songs(url)
        elif "/album/" in url:
            song_names = await self.spotify.get_album_songs(url)
        else:
            spotify_name = await self.spotify.get_track_name(url)
            song_names.append(spotify_name)

        # Always return a concrete list (the old code left `songs` unbound when
        # song_names was empty, raising UnboundLocalError).
        return [(song_name, message, True) for song_name in song_names]

    async def download_next_song(self):
        if len(self.queue) == 0:
            return

        pop_index = 0
        if self.state.playlist.shuffle:
            pop_index = random.randint(0, len(self.queue) - 1)

        next_song_name, message, spotify_req = self.queue.pop(pop_index)

        try:
            existing_reactions = [reaction.emoji for reaction in message.reactions]
            if PROCESSING not in existing_reactions:
                await message.add_reaction(PROCESSING)
        except Exception as e:
            self.logger.debug("Could not add loading reaction: %s", e)

        try:
            is_playable = await self.state.bot.loop.run_in_executor(
                self.executor, self.youtube.is_video_playable, next_song_name
            )
        except Exception:
            self.logger.exception("Error checking playability of %s", next_song_name)
            is_playable = False

        if not is_playable:
            sent_message = await message.channel.send(
                f"**{next_song_name}** is too long or there was an error "
                "downloading the song. Try another query."
            )
            await self.state.cog_failure(sent_message, message)
            return

        try:
            next_song_path, next_song_info = await self.state.bot.loop.run_in_executor(
                self.executor, self.youtube.download, next_song_name
            )
        except Exception:
            self.logger.exception("Error downloading %s", next_song_name)
            sent_message = await message.channel.send(
                f"**{next_song_name}** is too long or there was an error "
                "downloading the song. Try another query."
            )
            await self.state.cog_failure(sent_message, message)
            return

        if all(message is not item[1] for item in self.queue):
            await self.state.cog_success(message)

        if self.queue_cancelled:
            self.set_queue_cancelled(False)
            self.process_queue.stop()
            await self.state.state_machine.stop()
        else:
            lyrics = None
            if spotify_req:
                lyrics = await self.genius.fetch_lyrics(next_song_name)
                next_song_name = f"{next_song_name} audio"
            await self.state.playlist.add(
                next_song_path, next_song_info, message, lyrics
            )

        await self.state.playlist.update_message()

    async def enqueue(self, query, message):
        if "spotify.com" in query:
            songs = await self.get_spotify_songs(query, message)
        else:
            songs = [(query, message, False)]

        for song in songs:
            if song not in self.queue:
                playlist = self.state.playlist
                combined_total = len(self.queue) + len(playlist.songs)
                if combined_total + 1 <= playlist.max_size:
                    self.queue.append(song)
                    if self.queue_cancelled:
                        self.set_queue_cancelled(False)

        if not self.process_queue.is_running():
            await self.download_next_song()
            self.process_queue.start()

        self.state.state_machine.start()

    async def clear(self):
        self.logger.info("Clearing download queue")
        self.set_queue([])
        self.set_queue_cancelled(True)

    async def stop(self):
        self.logger.info("Stopping downloader")
        if self.process_queue.is_running():
            self.process_queue.cancel()
        await self.clear()
        self.state.state_machine.transition_to(State.STOPPED)
