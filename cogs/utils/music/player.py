import logging

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
        if self.music.state_machine.state == State.PLAYING:
            return

        self.music.state_machine.set_state(State.PLAYING)
        self.play_audio(song.path)
        self.music.playlist.set_current_song(song)
        self.logger.info(f"Playing song: {song.title}")
        await self.music.playlist.update_message()

        if not song.messages_to_delete:
            # Send embed
            embed = await self.music.playlist.send_song_embed(song)
            if embed:
                song.messages_to_delete.append(embed)

        if all(
            song.message is not item[1] for item in self.music.downloader.queue
        ) and all(
            song.message is not song.message for song in self.music.playlist.songs
        ):
            # Song/Playlist download completed
            song.messages_to_delete.append(song.message)

        # Set last song
        self.music.playlist.set_last_song(song)

        # Save statistics data on db
        self.music.bot.get_cog("Database").save_song(song.info, song.message.author.id)

        # Cleanup
        self.music.cleanup_files(song, self.music.playlist.songs)

    async def join_voice_channel(self, message):
        if self.music.state_machine.state == State.DISCONNECTED:
            voice_channel = message.author.voice.channel
            try:
                self.voice_client = await voice_channel.connect()
            except:
                return

            self.music.state_machine.set_state(State.STOPPED)

            return self.voice_client

    def play_audio(self, song_path):
        self.audio_source = discord.FFmpegPCMAudio(song_path)
        self.voice_client.play(self.audio_source)

    async def skip(self, message):
        if self.voice_client and self.voice_client.is_playing():
            self.logger.info("Skipping")
            self.voice_client.stop()
            await message.delete()

    def pause(self):
        if self.voice_client and not self.voice_client.is_paused():
            self.voice_client.pause()

    def resume(self):
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            self.end_timestamp = None

    def idle(self):
        vc = self.voice_client
        return vc and not vc.is_playing()
