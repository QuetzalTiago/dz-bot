import threading

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from cogs.models.song import Song
from cogs.utils.music.player import Player
from cogs.utils.music.state_machine import State


def make_song(path="song.mp3", message=None):
    info = {"title": "Test Song", "original_url": "https://example.com"}
    message = message or MagicMock()
    return Song(path, info, message)


@pytest.fixture
def state():
    state = MagicMock()
    state.state_machine.get_state.return_value = State.STOPPED
    state.playlist.songs = []
    state.playlist.update_message = AsyncMock()
    state.playlist.send_song_embed = AsyncMock(return_value=MagicMock())
    state.downloader.queue = []
    state.bot.get_cog.return_value = None
    return state


@pytest.fixture
def player(state):
    return Player(state)


# ---- play ------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_starts_playback_and_saves_stats(player, state):
    song = make_song()
    db = MagicMock()
    db.save_song = AsyncMock()
    state.bot.get_cog.return_value = db

    with patch.object(player, "play_audio") as play_audio:
        await player.play(song)

    play_audio.assert_called_once_with(song.path)
    state.playlist.set_current_song.assert_called_once_with(song)
    db.save_song.assert_awaited_once_with(song.info, song.message.author.id)
    state.cleanup_files.assert_called_once_with(song, state.playlist.songs)
    assert song.messages_to_delete.count(song.message) == 1


@pytest.mark.asyncio
async def test_play_offloads_cleanup_files_off_the_event_loop_thread(player, state):
    # Regression test: cleanup_files() does a directory scan plus per-file
    # os.remove() - it must run via asyncio.to_thread (like every other
    # blocking filesystem/DB call in this codebase), not directly on the
    # event loop thread, or it stalls all guilds' commands/voice heartbeats
    # on every song start.
    song = make_song()
    main_thread = threading.current_thread()
    seen_thread = None

    def fake_cleanup_files(current_song, queue):
        nonlocal seen_thread
        seen_thread = threading.current_thread()

    state.cleanup_files = fake_cleanup_files

    with patch.object(player, "play_audio"):
        await player.play(song)

    assert seen_thread is not None
    assert seen_thread is not main_thread


@pytest.mark.asyncio
async def test_play_resets_stale_end_timestamp(player, state):
    # Regression test: a stale end_timestamp left over from the idle gap
    # before this song started must be cleared - otherwise the very next
    # idle tick (once this song ends) computes elapsed_time against a
    # timestamp from long before this song even started playing, and the
    # idle timeout looks already-exceeded on its first tick.
    player.end_timestamp = 1.0
    song = make_song()

    with patch.object(player, "play_audio"):
        await player.play(song)

    assert player.end_timestamp is None


@pytest.mark.asyncio
async def test_play_does_not_log_stats_saved_when_database_unavailable(player, state):
    # Regression test: the "Song statistics saved" log line used to fire
    # unconditionally even when the Database cog wasn't loaded (get_cog
    # returns None) and save_song was never called - falsely claiming the
    # stats were persisted.
    song = make_song()
    state.bot.get_cog.return_value = None

    with patch.object(player, "play_audio"), patch.object(player, "logger") as logger:
        await player.play(song)

    assert not any(
        "statistics saved" in call.args[0] for call in logger.info.call_args_list
    )


@pytest.mark.asyncio
async def test_play_skips_when_already_playing(player, state):
    state.state_machine.get_state.return_value = State.PLAYING
    song = make_song()

    with patch.object(player, "play_audio") as play_audio:
        await player.play(song)

    play_audio.assert_not_called()
    state.playlist.set_current_song.assert_not_called()


@pytest.mark.asyncio
async def test_play_looped_song_does_not_duplicate_message_in_cleanup_list(
    player, state
):
    # Regression test: a looped song is replayed via the same Song object
    # every cycle. Without a membership guard, `song.message` was appended to
    # messages_to_delete on every replay, growing unbounded and causing a
    # pile of failing (but caught) delete() calls once the loop ended.
    song = make_song()

    with patch.object(player, "play_audio"):
        await player.play(song)
        await player.play(song)
        await player.play(song)

    assert song.messages_to_delete.count(song.message) == 1


@pytest.mark.asyncio
async def test_play_does_not_mark_message_pending_download(player, state):
    song = make_song()
    state.downloader.queue = [("other query", song.message, False)]

    with patch.object(player, "play_audio"):
        await player.play(song)

    assert song.message not in song.messages_to_delete


@pytest.mark.asyncio
async def test_play_does_not_mark_message_pending_in_playlist(player, state):
    song = make_song()
    other = MagicMock()
    other.message = song.message
    state.playlist.songs = [other]

    with patch.object(player, "play_audio"):
        await player.play(song)

    assert song.message not in song.messages_to_delete


# ---- play_audio --------------------------------------------------------


def test_play_audio_starts_ffmpeg_playback(player):
    vc = MagicMock()
    player.voice_client = vc
    with patch("cogs.utils.music.player.discord.FFmpegPCMAudio") as ffmpeg:
        player.play_audio("path.mp3")

    ffmpeg.assert_called_once_with("path.mp3")
    vc.play.assert_called_once_with(ffmpeg.return_value)
    assert player.audio_source is ffmpeg.return_value


# ---- idle / handle_idle --------------------------------------------------


def test_idle_true_when_voice_client_not_playing(player):
    player.voice_client = MagicMock()
    player.voice_client.is_playing.return_value = False
    assert player.idle() is True


def test_idle_false_when_voice_client_playing(player):
    player.voice_client = MagicMock()
    player.voice_client.is_playing.return_value = True
    assert player.idle() is False


def test_idle_false_when_no_voice_client(player):
    player.voice_client = None
    assert player.idle() is False


@pytest.mark.asyncio
async def test_handle_idle_stops_only_after_timeout_elapses(player, state):
    player.voice_client = MagicMock()
    player.voice_client.is_playing.return_value = False
    player.idle_timeout = 5
    state.stop = AsyncMock()

    with patch("cogs.utils.music.player.time.time", return_value=1000.0):
        await player.handle_idle()
    assert player.end_timestamp == 1000.0
    state.stop.assert_not_awaited()

    with patch("cogs.utils.music.player.time.time", return_value=1003.0):
        await player.handle_idle()
    state.stop.assert_not_awaited()

    with patch("cogs.utils.music.player.time.time", return_value=1006.0):
        await player.handle_idle()
    state.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_idle_noop_when_not_idle(player, state):
    player.voice_client = MagicMock()
    player.voice_client.is_playing.return_value = True
    state.stop = AsyncMock()

    await player.handle_idle()

    assert player.end_timestamp is None
    state.stop.assert_not_awaited()


# ---- pause / resume -------------------------------------------------------


def test_pause_when_playing(player):
    player.voice_client = MagicMock()
    player.voice_client.is_paused.return_value = False
    player.pause()
    player.voice_client.pause.assert_called_once()


def test_pause_noop_when_already_paused(player):
    player.voice_client = MagicMock()
    player.voice_client.is_paused.return_value = True
    player.pause()
    player.voice_client.pause.assert_not_called()


def test_resume_when_paused(player):
    player.voice_client = MagicMock()
    player.voice_client.is_paused.return_value = True
    player.end_timestamp = 123.0
    player.resume()
    player.voice_client.resume.assert_called_once()
    assert player.end_timestamp is None


def test_resume_noop_when_not_paused(player):
    player.voice_client = MagicMock()
    player.voice_client.is_paused.return_value = False
    player.resume()
    player.voice_client.resume.assert_not_called()


# ---- stop -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_disconnects_and_resets_state(player, state):
    vc = MagicMock()
    vc.is_playing.return_value = True
    vc.is_paused.return_value = False
    vc.disconnect = AsyncMock()
    player.voice_client = vc
    state.playlist.clear = AsyncMock()

    await player.stop()

    vc.stop.assert_called_once()
    vc.disconnect.assert_awaited_once()
    assert player.voice_client is None
    state.state_machine.set_state.assert_called_once_with(State.DISCONNECTED)
    state.playlist.clear.assert_awaited_once()
    assert player.end_timestamp is None
    assert player.audio_source is None


@pytest.mark.asyncio
async def test_stop_noop_without_voice_client(player, state):
    player.voice_client = None
    await player.stop()
    state.state_machine.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_stop_continues_if_disconnect_raises(player, state):
    vc = MagicMock()
    vc.is_playing.return_value = False
    vc.is_paused.return_value = False
    vc.disconnect = AsyncMock(side_effect=discord.DiscordException("boom"))
    player.voice_client = vc
    state.playlist.clear = AsyncMock()

    await player.stop()

    assert player.voice_client is None


# ---- skip -------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_stops_playback_and_deletes_message(player):
    vc = MagicMock()
    vc.is_playing.return_value = True
    player.voice_client = vc
    message = MagicMock()
    message.delete = AsyncMock()

    await player.skip(message)

    vc.stop.assert_called_once()
    message.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_skip_noop_when_not_playing(player):
    vc = MagicMock()
    vc.is_playing.return_value = False
    player.voice_client = vc
    message = MagicMock()
    message.delete = AsyncMock()

    await player.skip(message)

    vc.stop.assert_not_called()
    message.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_skip_handles_delete_failure(player):
    vc = MagicMock()
    vc.is_playing.return_value = True
    player.voice_client = vc
    message = MagicMock()
    message.delete = AsyncMock(side_effect=discord.DiscordException("gone"))

    await player.skip(message)  # should not raise


# ---- join_voice_channel -----------------------------------------------


@pytest.mark.asyncio
async def test_join_voice_channel_connects_when_disconnected(player, state):
    state.state_machine.get_state.return_value = State.DISCONNECTED
    message = MagicMock()
    voice_channel = MagicMock()
    voice_channel.connect = AsyncMock(return_value=MagicMock())
    message.author.voice.channel = voice_channel

    result = await player.join_voice_channel(message)

    voice_channel.connect.assert_awaited_once()
    assert result is voice_channel.connect.return_value
    state.state_machine.transition_to.assert_called_once_with(State.STOPPED)


@pytest.mark.asyncio
async def test_join_voice_channel_returns_none_when_author_not_in_voice(
    player, state
):
    state.state_machine.get_state.return_value = State.DISCONNECTED
    message = MagicMock()
    message.author.voice = None

    result = await player.join_voice_channel(message)

    assert result is None


@pytest.mark.asyncio
async def test_join_voice_channel_noop_when_not_disconnected(player, state):
    state.state_machine.get_state.return_value = State.PLAYING
    message = MagicMock()

    result = await player.join_voice_channel(message)

    assert result is None


@pytest.mark.asyncio
async def test_join_voice_channel_returns_existing_client_when_already_connected(
    player, state
):
    # Regression test: an already-connected bot (not DISCONNECTED) must report
    # success via its existing voice client, not None - callers (e.g.
    # Playlist.add) treat None as "failed to join" and would otherwise drop
    # the song even though the bot is already in the channel.
    state.state_machine.get_state.return_value = State.PLAYING
    player.voice_client = MagicMock()
    message = MagicMock()

    result = await player.join_voice_channel(message)

    assert result is player.voice_client


@pytest.mark.asyncio
async def test_join_voice_channel_handles_connect_failure(player, state):
    state.state_machine.get_state.return_value = State.DISCONNECTED
    message = MagicMock()
    voice_channel = MagicMock()
    voice_channel.connect = AsyncMock(side_effect=discord.DiscordException("nope"))
    message.author.voice.channel = voice_channel

    result = await player.join_voice_channel(message)

    assert result is None
    assert player.voice_client is None
