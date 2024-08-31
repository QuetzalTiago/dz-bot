from enum import Enum
from discord.ext import tasks
import time
import logging


class State(Enum):
    IDLE = "idle"
    PLAYING = "playing"
    STOPPED = "stopped"
    DISCONNECTED = "disconnected"
    PAUSED = "paused"
    RESUMED = "resumed"


class StateMachine:
    def __init__(self, music):
        self.music = music
        self.state = State.DISCONNECTED
        self.music_end_timestamp = None
        self.idle_timeout = 150
        self.logger = logging.getLogger("discord")

    def set_state(self, state):
        self.state = state
        self.logger.info(f"State changed to: {state}")

    def start(self):
        if not self.handle_state.is_running():
            self.handle_state.start()
            self.logger.info("State handling loop started.")

    def stop(self):
        if self.handle_state.is_running():
            self.handle_state.stop()
            self.logger.info("State handling loop stopped.")

    @tasks.loop(seconds=2)
    async def handle_state(self):
        self.logger.debug(f"Handling state: {self.state}")
        if self.state == State.DISCONNECTED:
            return

        if self.state == State.PLAYING:
            current_song = self.music.playlist.current_song
            if current_song:
                await self.music.playlist.update_song_message(current_song)

            if self.music.voice_client and not self.music.voice_client.is_playing():
                self.music.playlist.clear_last()
                self.set_state(State.STOPPED)

        if self.state == State.STOPPED:
            if self.music.playlist.empty():
                self.set_state(State.IDLE)
            else:
                next_song = await self.music.playlist.get_next()
                await self.music.play_song(next_song)

        if self.state == State.PAUSED:
            if self.music.voice_client and not self.music.voice_client.is_paused():
                self.music.voice_client.pause()

        if self.state == State.RESUMED:
            if self.music.voice_client and self.music.voice_client.is_paused():
                self.music.voice_client.resume()
                self.music_end_timestamp = None
                self.set_state(State.PLAYING)

        if self.state == State.IDLE or self.state == State.PAUSED:
            if self.music_end_timestamp is None:
                self.music_end_timestamp = time.time()
            elif time.time() - self.music_end_timestamp >= self.idle_timeout:
                await self.music.stop(None)
                self.music_end_timestamp = None

        if self.music.voice_client and self.music.voice_client.channel:
            members_in_channel = len(self.music.voice_client.channel.members)
            if members_in_channel == 1:
                await self.music.stop(None)
                await self.music.clear(None)

    @handle_state.before_loop
    async def before_handle_state(self):
        await self.music.bot.wait_until_ready()
        self.logger.info("Bot is ready, starting state handling loop.")
