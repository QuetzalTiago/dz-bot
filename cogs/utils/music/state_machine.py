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
        self.__state = State.DISCONNECTED
        self.logger = logging.getLogger("discord")

        self.valid_transitions = {
            State.DISCONNECTED: [State.STOPPED],
            State.STOPPED: [State.PLAYING, State.DISCONNECTED],
            State.PLAYING: [State.PAUSED, State.STOPPED],
            State.PAUSED: [State.RESUMED, State.STOPPED],
            State.RESUMED: [State.PLAYING],
        }

    @property
    def state(self):
        return self.__state

    def get_state(self) -> State:
        return self.__state

    def transition_to(self, new_state):
        current_state = self.__state
        if new_state in self.valid_transitions.get(current_state, []):
            self.__state = new_state
            self.logger.info(f"Valid transition: {current_state} -> {new_state}")
        else:
            self.logger.warning(
                f"Invalid transition attempted: {current_state} -> {new_state}"
            )

    def start(self):
        if not self.handle_state.is_running():
            self.handle_state.start()
            self.logger.info("State machine loop started.")

    async def stop(self):
        if self.handle_state.is_running():
            self.handle_state.stop()
            self.logger.info("State machine loop stopped.")

    @tasks.loop(seconds=2)
    async def handle_state(self):
        player = self.music.player
        playlist = self.music.playlist

        self.logger.debug(f"Current state: {self.state}")

        if self.state == State.DISCONNECTED:
            return

        if self.state == State.PLAYING:
            await playlist.update_curr_song_message()

            if player.idle():
                await playlist.clear_last()
                self.transition_to(State.STOPPED)

        if self.state == State.STOPPED:
            if playlist.empty():
                await player.handle_idle()
            else:
                next_song = await playlist.get_next()
                await player.play(next_song)
                self.transition_to(State.PLAYING)

        if self.state == State.PAUSED:
            await player.pause()
            await player.handle_idle()

        if self.state == State.RESUMED:
            await player.resume()
            self.transition_to(State.PLAYING)

        if player.voice_client and player.voice_client.channel:
            members_in_channel = len(player.voice_client.channel.members)
            if members_in_channel == 1:
                await self.music.stop(None)
                await self.music.clear(None)
                self.transition_to(State.DISCONNECTED)

    @handle_state.before_loop
    async def before_handle_state(self):
        await self.music.bot.wait_until_ready()
