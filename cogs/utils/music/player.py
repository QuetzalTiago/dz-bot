import logging
import time

import discord

from cogs.api.genius import GeniusAPI
from cogs.api.spotify import SpotifyAPI
from cogs.api.youtube import YouTubeAPI
from cogs.models.song import Song
from cogs.utils.music.state_machine import State


class Player:
    def __init__(self, music):
        self.music = music
        self.voice_client = None
        self.end_timestamp = None
        self.idle_timeout = 150
        self.audio_source = None
        self.logger = logging.getLogger("discord")

    async def play(self, song: Song):
        if self.music.state_machine.get_state() == State.PLAYING:
            self.logger.warn("Already playing a song, skipping play request.")
            return

        self.logger.info("Starting playback")
        self.play_audio(song.path)
        self.music.playlist.set_current_song(song)
        self.logger.info(f"Playing song: {song.title}")

        await self.music.playlist.update_message()

        if not song.messages_to_delete:
            embed = await self.music.playlist.send_song_embed(song)
            if embed:
                song.messages_to_delete.append(embed)
                self.logger.debug(f"Embed sent for song: {song.title}")

        if all(
            song.message is not item[1] for item in self.music.downloader.queue
        ) and all(
            song.message is not song.message for song in self.music.playlist.songs
        ):
            self.logger.info("Song or playlist download completed.")
            song.messages_to_delete.append(song.message)

        self.music.playlist.set_last_song(song)
        self.logger.debug("Set last played song: %s", song.title)

        self.music.bot.get_cog("Database").save_song(song.info, song.message.author.id)
        self.logger.info("Song statistics saved for %s", song.title)

        self.music.cleanup_files(song, self.music.playlist.songs)
        self.logger.debug("Cleaned up files for song: %s", song.title)

    async def join_voice_channel(self, message):
        if self.music.state_machine.get_state() == State.DISCONNECTED:
            voice_channel = message.author.voice.channel
            self.logger.info(
                f"Joining voice channel: {voice_channel.name} (ID: {voice_channel.id})"
            )

            try:
                self.voice_client = await voice_channel.connect()
                self.logger.info(f"Connected to voice channel: {voice_channel.name}")
            except discord.DiscordException as e:
                self.logger.error(
                    f"Failed to connect to voice channel: {voice_channel.name}, Error: {e}",
                    exc_info=True,
                )
                return

            self.music.state_machine.transition_to(State.STOPPED)
            return self.voice_client

    def play_audio(self, song_path):
        self.logger.debug("Playing audio for song path: %s", song_path)
        self.audio_source = discord.FFmpegPCMAudio(song_path)
        self.voice_client.play(self.audio_source)
        self.logger.info(f"Audio playback started")

    async def skip(self, message):
        if self.voice_client and self.voice_client.is_playing():
            self.logger.info("Skipping the current song.")
            self.voice_client.stop()
            await message.delete()
            self.logger.debug("Deleted the skip request message.")

    def pause(self):
        if self.voice_client and not self.voice_client.is_paused():
            self.logger.info("Pausing playback.")
            self.voice_client.pause()

    def resume(self):
        if self.voice_client and self.voice_client.is_paused():
            self.logger.info("Resuming playback.")
            self.voice_client.resume()
            self.end_timestamp = None

    def idle(self):
        vc = self.voice_client
        return vc is not None and not vc.is_playing()

    async def handle_idle(self):
        if self.idle():
            curr_timestamp = time.time()
            self.logger.debug("Idle detected. Current timestamp: %s", curr_timestamp)

            if self.end_timestamp is None:
                self.end_timestamp = curr_timestamp
                self.logger.info("Set end_timestamp: %s", self.end_timestamp)
            else:
                elapsed_time = curr_timestamp - self.end_timestamp
                self.logger.debug("Time elapsed since idle: %s seconds", elapsed_time)

                if elapsed_time >= self.idle_timeout:
                    self.logger.info(
                        f"Idle timeout reached: {self.idle_timeout} seconds, stopping music."
                    )
                    await self.music.stop(None)

    async def stop(self):
        if self.voice_client:
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self.voice_client.stop()
                self.logger.info("Stopped audio playback.")

            await self.voice_client.disconnect()
            self.voice_client = None
            self.logger.info("Disconnected from the voice channel.")

            self.music.state_machine.transition_to(State.DISCONNECTED)
            self.music.playlist.clear()

            self.end_timestamp = None
            self.audio_source = None
            self.logger.debug("Cleared playlist, reset end_timestamp and audio_source.")
