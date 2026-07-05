import logging
from enum import Enum

from discord.ext import tasks


class State(Enum):
    PLAYING = "playing"
    STOPPED = "stopped"
    DISCONNECTED = "disconnected"
    PAUSED = "paused"
    RESUMED = "resumed"


class StateMachine:
    def __init__(self, state):
        # `state` is the per-guild GuildMusicState.
        self.state = state
        self.__state = State.DISCONNECTED
        self.logger = logging.getLogger("discord")

        self.valid_transitions = {
            # DISCONNECTED can always be reached (stop/kick) from any state.
            State.DISCONNECTED: [State.STOPPED],
            State.STOPPED: [State.PLAYING, State.DISCONNECTED],
            State.PLAYING: [State.PAUSED, State.STOPPED, State.DISCONNECTED],
            State.PAUSED: [State.RESUMED, State.STOPPED, State.DISCONNECTED],
            State.RESUMED: [State.PLAYING, State.STOPPED, State.DISCONNECTED],
        }

    @property
    def current(self):
        return self.__state

    def get_state(self) -> State:
        return self.__state

    def set_state(self, new_state: State):
        """Force a state without transition validation (recovery/teardown)."""
        self.__state = new_state

    def transition_to(self, new_state):
        current_state = self.__state
        if new_state in self.valid_transitions.get(current_state, []):
            self.__state = new_state
            self.logger.info(f"State transition: {current_state} -> {new_state}")
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
            # `stop()` (not `cancel()`): this is routinely invoked from inside
            # the loop's own currently-running tick (e.g. via handle_idle()),
            # and cancel() would deliver CancelledError into that same task at
            # its next await, aborting the cleanup calls that follow.
            self.handle_state.stop()
            self.logger.info("State machine loop stopped.")

    @tasks.loop(seconds=2)
    async def handle_state(self):
        # Entire body guarded so a transient error can't permanently kill the
        # loop (a bare tasks.loop stops for good on the first exception).
        try:
            await self._tick()
        except Exception:
            self.logger.exception("Error in music state machine tick")

    async def _tick(self):
        player = self.state.player
        playlist = self.state.playlist
        state = self.current

        # Reconcile with the real voice client: if we think we're connected but
        # the client is gone, recover to a clean STOPPED/DISCONNECTED state.
        if state in (State.PLAYING, State.PAUSED, State.RESUMED):
            if player.voice_client is None or not player.voice_client.is_connected():
                self.logger.warning("Voice client lost; resetting state machine.")
                await playlist.clear()
                self.set_state(State.DISCONNECTED)
                await self.stop()
                return

        match state:
            case State.PLAYING:
                await playlist.update_curr_song_message()
                if player.idle():
                    await playlist.clear_last()
                    self.transition_to(State.STOPPED)

            case State.STOPPED:
                if playlist.empty():
                    await player.handle_idle()
                else:
                    next_song = await playlist.get_next()
                    if next_song is not None:
                        await player.play(next_song)
                        self.transition_to(State.PLAYING)

            case State.PAUSED:
                player.pause()
                await player.handle_idle()

            case State.RESUMED:
                player.resume()
                self.transition_to(State.PLAYING)

            case _:
                return

        # If the bot is alone in the channel, stop and disconnect.
        if player.voice_client and player.voice_client.channel:
            members = player.voice_client.channel.members
            if len([m for m in members if not m.bot]) == 0:
                await self.state.stop()
                self.set_state(State.DISCONNECTED)

    @handle_state.before_loop
    async def before_handle_state(self):
        await self.state.bot.wait_until_ready()
