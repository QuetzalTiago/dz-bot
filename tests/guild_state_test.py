import asyncio
import contextlib
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from cogs.utils.music.guild_state import GuildMusicState
from cogs.utils.music.state_machine import State


class FakeVoiceClient:
    """A voice client whose disconnect() has a genuine suspension point,
    like the real discord.py implementation (it awaits network I/O)."""

    def __init__(self):
        self.disconnected = False

    def is_connected(self):
        return True

    def is_playing(self):
        return False

    def is_paused(self):
        return False

    def stop(self):
        pass

    async def disconnect(self):
        await asyncio.sleep(0.01)
        self.disconnected = True


@pytest.fixture
def guild_state():
    cog = MagicMock()
    cog.bot = MagicMock()
    cog.bot.wait_until_ready = AsyncMock()
    cog.config = {
        "secrets": {
            "spotifyClientId": "x",
            "spotifyClientSecret": "x",
            "geniusApiKey": "x",
        }
    }
    guild = MagicMock()
    return GuildMusicState(cog, guild)


@pytest.mark.asyncio
async def test_cog_success_proxies_to_cog(guild_state):
    guild_state.cog.cog_success = AsyncMock()
    message = MagicMock()

    await guild_state.cog_success(message)

    guild_state.cog.cog_success.assert_awaited_once_with(message)


@pytest.mark.asyncio
async def test_cog_failure_proxies_to_cog(guild_state):
    guild_state.cog.cog_failure = AsyncMock()
    sent_message = MagicMock()
    query_message = MagicMock()

    await guild_state.cog_failure(sent_message, query_message)

    guild_state.cog.cog_failure.assert_awaited_once_with(sent_message, query_message)


def test_cleanup_files_proxies_to_cog(guild_state):
    current_song = MagicMock()
    queue = [MagicMock()]

    guild_state.cleanup_files(current_song, queue)

    guild_state.cog.cleanup_files.assert_called_once_with(current_song, queue)


@pytest.mark.asyncio
async def test_teardown_stops_state_machine_and_clears_everything(guild_state):
    guild_state.state_machine.stop = AsyncMock()
    guild_state.downloader.clear = AsyncMock()
    guild_state.player.stop = AsyncMock()
    guild_state.playlist.clear = AsyncMock()

    await guild_state.teardown()

    guild_state.state_machine.stop.assert_awaited_once()
    guild_state.downloader.clear.assert_awaited_once()
    guild_state.player.stop.assert_awaited_once()
    guild_state.playlist.clear.assert_awaited_once()
    assert guild_state.state_machine.current == State.DISCONNECTED


@pytest.mark.asyncio
async def test_idle_timeout_auto_stop_completes_full_cleanup(guild_state):
    # Regression test: GuildMusicState.stop() used to cancel the state
    # machine's own `handle_state` loop task *before* running the rest of
    # cleanup. That loop task is the one executing this exact code path when
    # stop() is triggered by an idle timeout (or "alone in channel"), so the
    # self-cancellation aborted everything after the next genuine suspension
    # point - player.stop()'s `await voice_client.disconnect()` - leaving
    # voice_client non-None, the download queue uncleared, and the state
    # machine stuck reporting STOPPED instead of DISCONNECTED.
    fake_vc = FakeVoiceClient()
    guild_state.player.voice_client = fake_vc
    guild_state.player.idle_timeout = 0
    guild_state.player.end_timestamp = time.time() - 10  # already past timeout

    guild_state.playlist.songs = []  # empty() -> True, so the STOPPED tick
    # goes through handle_idle() instead of trying to play a next song.
    guild_state.downloader.queue = [("song", MagicMock(), False)]

    guild_state.state_machine.set_state(State.STOPPED)
    guild_state.state_machine.handle_state.start()
    try:
        await asyncio.sleep(0.2)

        assert fake_vc.disconnected is True
        assert guild_state.player.voice_client is None
        assert guild_state.downloader.queue == []
        assert guild_state.state_machine.current == State.DISCONNECTED
    finally:
        task = guild_state.state_machine.handle_state.get_task()
        guild_state.state_machine.handle_state.cancel()
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await task
