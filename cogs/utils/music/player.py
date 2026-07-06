import logging
import time

import discord

from cogs.models.song import Song
from cogs.utils.music.state_machine import State


class Player:
    def __init__(self, state):
        # `state` is the per-guild GuildMusicState.
        self.state = state
        self.voice_client = None
        self.end_timestamp = None
        self.idle_timeout = 300
        self.audio_source = None
        self.logger = logging.getLogger("discord")

    async def play(self, song: Song):
        if self.state.state_machine.get_state() == State.PLAYING:
            self.logger.warning("Already playing a song, skipping play request.")
            return

        playlist = self.state.playlist
        self.logger.info("Starting playback")
        self.play_audio(song.path)
        # A stale end_timestamp from the idle gap before this song started
        # would otherwise make the next idle period look like it's already
        # exceeded idle_timeout on its very first tick.
        self.end_timestamp = None
        playlist.set_current_song(song)
        self.logger.info(f"Playing song: {song.title}")

        await playlist.update_message()

        if not song.messages_to_delete:
            embed = await playlist.send_song_embed(song)
            if embed:
                song.messages_to_delete.append(embed)

        # Mark the request message for later cleanup once the song is no longer
        # queued for download and isn't still pending in the playlist.
        pending_download = any(
            song.message is item[1] for item in self.state.downloader.queue
        )
        pending_in_playlist = any(song.message is s.message for s in playlist.songs)
        # A looped song replays the same Song object each cycle; without the
        # membership check this appends a duplicate every replay, and each
        # duplicate turns into a wasted (and logged) failing delete() once the
        # song is finally cleaned up.
        if (
            not pending_download
            and not pending_in_playlist
            and song.message not in song.messages_to_delete
        ):
            song.messages_to_delete.append(song.message)

        playlist.set_last_song(song)

        db = self.state.bot.get_cog("Database")
        if db is not None:
            await db.save_song(song.info, song.message.author.id)
            self.logger.info("Song statistics saved for %s", song.title)

        self.state.cleanup_files(song, playlist.songs)

    async def join_voice_channel(self, message):
        """Ensure the bot is connected, returning the voice client on success.

        Returns None only on an actual failure (requester not in a voice
        channel, or the connect attempt raised) - callers must treat None as
        "did not join" rather than "already connected".
        """
        if self.state.state_machine.get_state() != State.DISCONNECTED:
            return self.voice_client
        if message.author.voice is None:
            self.logger.warning("Requester is not in a voice channel.")
            return None
        voice_channel = message.author.voice.channel
        self.logger.info(f"Joining voice channel: {voice_channel.name}")
        try:
            self.voice_client = await voice_channel.connect()
        except discord.DiscordException as e:
            self.logger.error(
                "Failed to connect to voice channel %s: %s",
                voice_channel.name,
                e,
                exc_info=True,
            )
            return None
        self.state.state_machine.transition_to(State.STOPPED)
        return self.voice_client

    def play_audio(self, song_path):
        self.logger.debug("Playing audio for song path: %s", song_path)
        self.audio_source = discord.FFmpegPCMAudio(song_path)
        self.voice_client.play(self.audio_source)
        self.logger.info("Audio playback started")

    async def skip(self, message):
        if self.voice_client and self.voice_client.is_playing():
            self.logger.info("Skipping the current song.")
            self.voice_client.stop()
            try:
                await message.delete()
            except discord.DiscordException as e:
                self.logger.warning("Failed to delete skip message: %s", e)

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
            if self.end_timestamp is None:
                self.end_timestamp = curr_timestamp
            else:
                elapsed_time = curr_timestamp - self.end_timestamp
                if elapsed_time >= self.idle_timeout:
                    self.logger.info(
                        "Idle timeout reached (%ss); stopping music.",
                        self.idle_timeout,
                    )
                    await self.state.stop()

    async def stop(self):
        if self.voice_client:
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self.voice_client.stop()
                self.logger.info("Stopped audio playback.")
            try:
                await self.voice_client.disconnect()
            except discord.DiscordException as e:
                self.logger.warning("Error disconnecting voice client: %s", e)
            self.voice_client = None
            self.logger.info("Disconnected from the voice channel.")

            self.state.state_machine.set_state(State.DISCONNECTED)
            await self.state.playlist.clear()

            self.end_timestamp = None
            self.audio_source = None
