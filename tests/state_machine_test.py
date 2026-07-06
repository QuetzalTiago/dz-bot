import pytest
from unittest.mock import AsyncMock, MagicMock

from cogs.utils.music.state_machine import State, StateMachine


def make_state_machine():
    state = MagicMock()
    state.player = MagicMock()
    state.playlist = MagicMock()
    state.downloader = MagicMock()
    state.stop = AsyncMock()

    state.playlist.update_curr_song_message = AsyncMock()
    state.playlist.clear_last = AsyncMock()
    state.playlist.clear = AsyncMock()
    state.playlist.get_next = AsyncMock(return_value=None)

    state.player.play = AsyncMock()
    state.player.handle_idle = AsyncMock()

    sm = StateMachine(state)
    return sm, state


def test_transition_to_allows_valid_transition():
    sm, _ = make_state_machine()
    sm.set_state(State.STOPPED)

    sm.transition_to(State.PLAYING)

    assert sm.current == State.PLAYING


def test_transition_to_rejects_invalid_transition():
    sm, _ = make_state_machine()
    sm.set_state(State.DISCONNECTED)

    # DISCONNECTED can only move to STOPPED - PLAYING must be rejected.
    sm.transition_to(State.PLAYING)

    assert sm.current == State.DISCONNECTED


def test_start_does_not_restart_running_loop():
    sm, _ = make_state_machine()
    sm.handle_state.is_running = MagicMock(return_value=True)
    sm.handle_state.start = MagicMock()

    sm.start()

    sm.handle_state.start.assert_not_called()


def test_start_starts_stopped_loop():
    sm, _ = make_state_machine()
    sm.handle_state.is_running = MagicMock(return_value=False)
    sm.handle_state.start = MagicMock()

    sm.start()

    sm.handle_state.start.assert_called_once()


@pytest.mark.asyncio
async def test_stop_cancels_running_loop():
    sm, _ = make_state_machine()
    sm.handle_state.is_running = MagicMock(return_value=True)
    sm.handle_state.cancel = MagicMock()

    await sm.stop()

    sm.handle_state.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_tick_resets_to_disconnected_when_voice_client_lost():
    sm, state = make_state_machine()
    sm.set_state(State.PLAYING)
    state.player.voice_client = None

    await sm._tick()

    assert sm.current == State.DISCONNECTED
    state.playlist.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_tick_resets_to_disconnected_when_voice_client_disconnected():
    sm, state = make_state_machine()
    sm.set_state(State.PAUSED)
    state.player.voice_client = MagicMock()
    state.player.voice_client.is_connected.return_value = False

    await sm._tick()

    assert sm.current == State.DISCONNECTED


@pytest.mark.asyncio
async def test_tick_playing_transitions_to_stopped_when_idle():
    sm, state = make_state_machine()
    sm.set_state(State.PLAYING)
    state.player.voice_client = MagicMock()
    state.player.voice_client.is_connected.return_value = True
    state.player.voice_client.channel = None
    state.player.idle.return_value = True

    await sm._tick()

    state.playlist.update_curr_song_message.assert_awaited_once()
    state.playlist.clear_last.assert_awaited_once()
    assert sm.current == State.STOPPED


@pytest.mark.asyncio
async def test_tick_playing_stays_playing_when_not_idle():
    sm, state = make_state_machine()
    sm.set_state(State.PLAYING)
    state.player.voice_client = MagicMock()
    state.player.voice_client.is_connected.return_value = True
    state.player.voice_client.channel = None
    state.player.idle.return_value = False

    await sm._tick()

    state.playlist.clear_last.assert_not_awaited()
    assert sm.current == State.PLAYING


@pytest.mark.asyncio
async def test_tick_stopped_counts_idle_when_playlist_empty_and_no_download_in_flight():
    sm, state = make_state_machine()
    sm.set_state(State.STOPPED)
    state.player.voice_client = None
    state.playlist.empty.return_value = True
    state.downloader.process_queue.is_running.return_value = False

    await sm._tick()

    state.player.handle_idle.assert_awaited_once()


@pytest.mark.asyncio
async def test_tick_stopped_skips_idle_countdown_while_download_in_flight():
    """Regression test: a song finishing while the *next* one is still
    downloading must not start (or advance) the idle timeout, or a slow
    download can get the bot to self-disconnect and wipe the queue."""
    sm, state = make_state_machine()
    sm.set_state(State.STOPPED)
    state.player.voice_client = None
    state.playlist.empty.return_value = True
    state.downloader.process_queue.is_running.return_value = True

    await sm._tick()

    state.player.handle_idle.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_stopped_plays_next_song_when_playlist_not_empty():
    sm, state = make_state_machine()
    sm.set_state(State.STOPPED)
    state.player.voice_client = None
    state.playlist.empty.return_value = False
    next_song = MagicMock()
    state.playlist.get_next = AsyncMock(return_value=next_song)

    await sm._tick()

    state.player.play.assert_awaited_once_with(next_song)
    assert sm.current == State.PLAYING


@pytest.mark.asyncio
async def test_tick_stopped_does_not_transition_when_get_next_returns_none():
    sm, state = make_state_machine()
    sm.set_state(State.STOPPED)
    state.player.voice_client = None
    state.playlist.empty.return_value = False
    state.playlist.get_next = AsyncMock(return_value=None)

    await sm._tick()

    state.player.play.assert_not_awaited()
    assert sm.current == State.STOPPED


@pytest.mark.asyncio
async def test_tick_paused_pauses_and_handles_idle():
    sm, state = make_state_machine()
    sm.set_state(State.PAUSED)
    state.player.voice_client = MagicMock()
    state.player.voice_client.is_connected.return_value = True
    state.player.voice_client.channel = None

    await sm._tick()

    state.player.pause.assert_called_once()
    state.player.handle_idle.assert_awaited_once()


@pytest.mark.asyncio
async def test_tick_resumed_resumes_and_transitions_to_playing():
    sm, state = make_state_machine()
    sm.set_state(State.RESUMED)
    state.player.voice_client = MagicMock()
    state.player.voice_client.is_connected.return_value = True
    state.player.voice_client.channel = None

    await sm._tick()

    state.player.resume.assert_called_once()
    assert sm.current == State.PLAYING


@pytest.mark.asyncio
async def test_tick_disconnects_when_alone_in_voice_channel():
    sm, state = make_state_machine()
    sm.set_state(State.PLAYING)
    voice_client = MagicMock()
    voice_client.is_connected.return_value = True
    bot_member = MagicMock(bot=True)
    voice_client.channel = MagicMock(members=[bot_member])
    state.player.voice_client = voice_client
    state.player.idle.return_value = False

    await sm._tick()

    state.stop.assert_awaited_once()
    assert sm.current == State.DISCONNECTED


@pytest.mark.asyncio
async def test_tick_stays_connected_when_a_human_remains_in_channel():
    sm, state = make_state_machine()
    sm.set_state(State.PLAYING)
    voice_client = MagicMock()
    voice_client.is_connected.return_value = True
    human_member = MagicMock(bot=False)
    voice_client.channel = MagicMock(members=[human_member])
    state.player.voice_client = voice_client
    state.player.idle.return_value = False

    await sm._tick()

    state.stop.assert_not_awaited()
    assert sm.current == State.PLAYING
