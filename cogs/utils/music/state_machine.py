from enum import Enum
from discord.ext import tasks
import logging


class State(Enum):
    PLAYING = "playing"
    STOPPED = "stopped"
    DISCONNECTED = "disconnected"
    PAUSED = "paused"
    RESUMED = "resumed"


class StateMachine:
    def __init__(self, music):
        self.music = music
        self.state = State.DISCONNECTED
        self.idle_timeout = 150
        self.logger = logging.getLogger("discord")

    def set_state(self, state):
        self.state = state
        self.logger.info(f"State changed to: {state}")

    def start(self):
        if not self.handle_state.is_running():
            self.handle_state.start()
            self.logger.info("State machine loop started.")

    def stop(self):
        if self.handle_state.is_running():
            self.handle_state.stop()
            self.logger.info("State machine loop stopped.")

    @tasks.loop(seconds=2)
    async def handle_state(self):
        player = self.music.player
        playlist = self.music.playlist

        self.logger.info(f"Current state: {self.state}")
        if self.state == State.DISCONNECTED:
            return

        if self.state == State.PLAYING:
            await playlist.update_curr_song_message()

            if player.idle():
                playlist.clear_last()
                self.set_state(State.STOPPED)

        if self.state == State.STOPPED:
            if playlist.empty():
                await player.handle_idle()
            else:
                next_song = await playlist.get_next()
                await player.play(next_song)

        if self.state == State.PAUSED:
            player.pause()

        if self.state == State.RESUMED:
            player.resume()
            self.set_state(State.PLAYING)

        if self.state == State.PAUSED:
            await player.handle_idle()

        if player.voice_client and player.voice_client.channel:
            members_in_channel = len(player.voice_client.channel.members)
            if members_in_channel == 1:
                await self.music.stop(None)
                await self.music.clear(None)

    @handle_state.before_loop
    async def before_handle_state(self):
        await self.music.bot.wait_until_ready()
        self.logger.info("Starting state machine loop.")
