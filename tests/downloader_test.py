import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cogs.utils.music.downloader import Downloader


@pytest.fixture
def config():
    return {
        "secrets": {
            "spotifyClientId": "test",
            "spotifyClientSecret": "test",
            "geniusApiKey": "test",
        }
    }


@pytest.fixture
def state(config):
    state = MagicMock()
    state.config = config
    state.playlist.songs = []
    state.playlist.max_size = 100
    return state


@pytest.fixture
def downloader(state):
    d = Downloader(state)
    yield d
    task = d.process_queue.get_task()
    if task is not None:
        d.process_queue.cancel()


async def cancel_and_wait(loop_task):
    task = loop_task.get_task()
    loop_task.cancel()
    if task is not None:
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_concurrent_enqueue_does_not_double_start_the_loop(downloader):
    # Regression test: two `play` invocations for the same guild can call
    # enqueue() concurrently. Before the enqueue()-internal lock, both could
    # observe process_queue.is_running() as False across the
    # `await download_next_song()` gap, and the second .start() would raise
    # RuntimeError ("Task is already launched").
    release = asyncio.Event()

    async def slow_download_next_song():
        await release.wait()

    downloader.download_next_song = AsyncMock(side_effect=slow_download_next_song)

    first = asyncio.ensure_future(downloader.enqueue("song one", MagicMock()))
    second = asyncio.ensure_future(downloader.enqueue("song two", MagicMock()))

    await asyncio.sleep(0)  # let both tasks reach the await inside download_next_song
    release.set()

    await asyncio.gather(first, second)  # must not raise RuntimeError

    assert downloader.process_queue.is_running()
    await cancel_and_wait(downloader.process_queue)


@pytest.mark.asyncio
async def test_download_next_song_cleans_up_when_queue_cancelled_mid_download(
    downloader, state
):
    # Regression test: if the queue is cancelled while a download is in
    # flight, the finished file must not leak on disk and the message must
    # not get a false "success" reaction for a song that will never play.
    message = MagicMock()
    message.reactions = []
    message.add_reaction = AsyncMock()
    message.clear_reactions = AsyncMock()
    message.channel.send = AsyncMock()

    downloader.queue = [("some song", message, False)]
    downloader.queue_cancelled = True

    state.bot.loop.run_in_executor = AsyncMock(
        side_effect=[True, ("downloads/12345.mp3", {"title": "Some Song"})]
    )
    state.state_machine.stop = AsyncMock()
    state.cog_success = AsyncMock()
    state.playlist.add = AsyncMock()
    state.playlist.update_message = AsyncMock()

    with patch("cogs.utils.music.downloader.os.remove") as mock_remove:
        await downloader.download_next_song()

    mock_remove.assert_called_once_with("downloads/12345.mp3")
    state.cog_success.assert_not_awaited()
    state.playlist.add.assert_not_awaited()
    assert downloader.queue_cancelled is False
    # Regression: the requester's message must not be left with a stuck
    # PROCESSING reaction forever with no success/error indicator.
    message.clear_reactions.assert_awaited_once()
    # Regression: a cancelled queue (e.g. from a plain `clear`) must not stop
    # the state machine - it may still be actively playing a previous song,
    # and stopping it would silently kill that playback's progress/idle-
    # timeout tracking until the next `play` restarts the loop.
    state.state_machine.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_next_song_does_not_react_success_when_playlist_drops_it(
    downloader, state
):
    # Regression test: the requester's message used to get a "done" reaction
    # (and no error) even when playlist.add() silently dropped the song
    # (e.g. the requester left voice while the download was in flight).
    message = MagicMock()
    message.reactions = []
    message.add_reaction = AsyncMock()
    message.channel.send = AsyncMock()

    downloader.queue = [("some song", message, False)]

    state.bot.loop.run_in_executor = AsyncMock(
        side_effect=[True, ("downloads/12345.mp3", {"title": "Some Song"})]
    )
    state.cog_success = AsyncMock()
    state.cog_failure = AsyncMock()
    state.playlist.add = AsyncMock(return_value=False)
    state.playlist.update_message = AsyncMock()

    await downloader.download_next_song()

    state.playlist.add.assert_awaited_once()
    state.cog_success.assert_not_awaited()
    state.cog_failure.assert_awaited_once()
    message.channel.send.assert_awaited_once()
    state.playlist.update_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_next_song_reacts_success_only_after_song_is_queued(
    downloader, state
):
    message = MagicMock()
    message.reactions = []
    message.add_reaction = AsyncMock()
    message.channel.send = AsyncMock()

    downloader.queue = [("some song", message, False)]

    state.bot.loop.run_in_executor = AsyncMock(
        side_effect=[True, ("downloads/12345.mp3", {"title": "Some Song"})]
    )
    state.cog_success = AsyncMock()
    state.cog_failure = AsyncMock()
    state.playlist.add = AsyncMock(return_value=True)
    state.playlist.update_message = AsyncMock()

    await downloader.download_next_song()

    state.playlist.add.assert_awaited_once()
    state.cog_success.assert_awaited_once_with(message)
    state.cog_failure.assert_not_awaited()
    state.playlist.update_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_next_song_reserves_path_while_fetching_lyrics(downloader, state):
    # Regression test: for a Spotify-sourced request, download_next_song()
    # awaits genius.fetch_lyrics() *after* the file is on disk but *before*
    # playlist.add() appends it to this guild's playlist - a yield point
    # another guild's cleanup_files() could run in. The path must be reserved
    # in the shared cog-level set for that whole window, and released once
    # add() resolves either way.
    message = MagicMock()
    message.reactions = []
    message.add_reaction = AsyncMock()
    message.channel.send = AsyncMock()

    downloader.queue = [("some song", message, True)]  # spotify_req=True

    state.bot.loop.run_in_executor = AsyncMock(
        side_effect=[True, ("downloads/12345.mp3", {"title": "Some Song"})]
    )
    state.cog.pending_download_paths = set()
    state.cog_success = AsyncMock()
    state.playlist.update_message = AsyncMock()

    path_reserved_during_fetch = None

    async def fetch_lyrics(_name):
        nonlocal path_reserved_during_fetch
        path_reserved_during_fetch = "downloads/12345.mp3" in state.cog.pending_download_paths
        return "some lyrics"

    async def add(*args, **kwargs):
        assert "downloads/12345.mp3" in state.cog.pending_download_paths
        return True

    downloader.genius.fetch_lyrics = fetch_lyrics
    state.playlist.add = add

    await downloader.download_next_song()

    assert path_reserved_during_fetch is True
    assert "downloads/12345.mp3" not in state.cog.pending_download_paths


@pytest.mark.asyncio
async def test_enqueue_notifies_when_queue_is_full(downloader, state):
    # Regression test: enqueue() used to silently drop songs that didn't fit
    # under playlist.max_size (e.g. a large Spotify playlist import), with no
    # indication to the requester that anything was left out.
    downloader.download_next_song = AsyncMock()
    state.playlist.max_size = 1
    downloader.queue = [("already queued song", MagicMock(), False)]

    message = MagicMock()
    message.channel.send = AsyncMock()

    await downloader.enqueue("some new song", message)

    assert ("some new song", message, False) not in downloader.queue
    message.channel.send.assert_awaited_once()
    assert "not added" in message.channel.send.call_args[0][0]
    await cancel_and_wait(downloader.process_queue)


@pytest.mark.asyncio
async def test_enqueue_does_not_notify_when_song_fits(downloader, state):
    downloader.download_next_song = AsyncMock()
    message = MagicMock()
    message.channel.send = AsyncMock()

    await downloader.enqueue("some new song", message)

    assert ("some new song", message, False) in downloader.queue
    message.channel.send.assert_not_awaited()
    await cancel_and_wait(downloader.process_queue)


@pytest.mark.asyncio
async def test_enqueue_clears_cancelled_flag_when_song_is_added(downloader, state):
    # A previous `clear` set queue_cancelled=True; a brand new enqueue() that
    # actually adds a song must un-cancel the queue so process_queue doesn't
    # immediately bail out on the next tick.
    downloader.download_next_song = AsyncMock()
    downloader.queue_cancelled = True
    message = MagicMock()
    message.channel.send = AsyncMock()

    await downloader.enqueue("brand new song", message)

    assert downloader.queue_cancelled is False
    await cancel_and_wait(downloader.process_queue)


@pytest.mark.asyncio
async def test_get_spotify_songs_playlist_url(downloader):
    downloader.spotify.get_playlist_songs = AsyncMock(return_value=["song a", "song b"])
    message = MagicMock()

    result = await downloader.get_spotify_songs(
        "https://open.spotify.com/playlist/xyz", message
    )

    downloader.spotify.get_playlist_songs.assert_awaited_once_with(
        "https://open.spotify.com/playlist/xyz"
    )
    assert result == [("song a", message, True), ("song b", message, True)]


@pytest.mark.asyncio
async def test_get_spotify_songs_album_url(downloader):
    downloader.spotify.get_album_songs = AsyncMock(return_value=["album song"])
    message = MagicMock()

    result = await downloader.get_spotify_songs(
        "https://open.spotify.com/album/xyz", message
    )

    downloader.spotify.get_album_songs.assert_awaited_once_with(
        "https://open.spotify.com/album/xyz"
    )
    assert result == [("album song", message, True)]


@pytest.mark.asyncio
async def test_get_spotify_songs_track_url(downloader):
    downloader.spotify.get_track_name = AsyncMock(return_value="track name")
    message = MagicMock()

    result = await downloader.get_spotify_songs(
        "https://open.spotify.com/track/xyz", message
    )

    downloader.spotify.get_track_name.assert_awaited_once_with(
        "https://open.spotify.com/track/xyz"
    )
    assert result == [("track name", message, True)]


@pytest.mark.asyncio
async def test_download_next_song_returns_immediately_when_queue_empty(downloader, state):
    downloader.queue = []
    state.bot.loop.run_in_executor = AsyncMock()

    await downloader.download_next_song()

    state.bot.loop.run_in_executor.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_next_song_swallows_reaction_add_failure(downloader, state):
    # A message with no `.reactions` iterable (or a reaction API error) must
    # not abort the download - the reaction is best-effort.
    message = MagicMock()
    message.reactions = []
    message.add_reaction = AsyncMock(side_effect=Exception("boom"))
    message.channel.send = AsyncMock()

    downloader.queue = [("some song", message, False)]
    state.bot.loop.run_in_executor = AsyncMock(
        side_effect=[True, ("downloads/12345.mp3", {"title": "Some Song"})]
    )
    state.cog.pending_download_paths = set()
    state.cog_success = AsyncMock()
    state.playlist.add = AsyncMock(return_value=True)
    state.playlist.update_message = AsyncMock()

    await downloader.download_next_song()

    state.cog_success.assert_awaited_once_with(message)


@pytest.mark.asyncio
async def test_download_next_song_treats_unplayable_as_failure(downloader, state):
    message = MagicMock()
    message.reactions = []
    message.add_reaction = AsyncMock()
    message.channel.send = AsyncMock(return_value="sent")

    downloader.queue = [("bad song", message, False)]
    state.bot.loop.run_in_executor = AsyncMock(return_value=False)
    state.cog_failure = AsyncMock()

    await downloader.download_next_song()

    state.cog_failure.assert_awaited_once_with("sent", message)
    assert "too long" in message.channel.send.call_args[0][0]


@pytest.mark.asyncio
async def test_download_next_song_handles_playability_check_exception(downloader, state):
    # An exception raised while checking playability (e.g. yt-dlp network
    # error) must be treated as "not playable", not crash the download loop.
    message = MagicMock()
    message.reactions = []
    message.add_reaction = AsyncMock()
    message.channel.send = AsyncMock(return_value="sent")

    downloader.queue = [("bad song", message, False)]
    state.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("network error"))
    state.cog_failure = AsyncMock()

    await downloader.download_next_song()

    state.cog_failure.assert_awaited_once_with("sent", message)


@pytest.mark.asyncio
async def test_download_next_song_handles_download_exception(downloader, state):
    message = MagicMock()
    message.reactions = []
    message.add_reaction = AsyncMock()
    message.channel.send = AsyncMock(return_value="sent")

    downloader.queue = [("some song", message, False)]
    state.bot.loop.run_in_executor = AsyncMock(
        side_effect=[True, Exception("disk full")]
    )
    state.cog_failure = AsyncMock()

    await downloader.download_next_song()

    state.cog_failure.assert_awaited_once_with("sent", message)


@pytest.mark.asyncio
async def test_process_queue_stops_when_queue_empty(downloader):
    downloader.queue = []
    downloader.download_next_song = AsyncMock()

    await downloader.process_queue.coro(downloader)

    downloader.download_next_song.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_queue_logs_and_survives_download_exception(downloader):
    downloader.queue = [("song", MagicMock(), False)]
    downloader.download_next_song = AsyncMock(side_effect=Exception("boom"))

    # Must not raise - a bare tasks.loop stops for good on the first
    # unhandled exception, which would silently kill the download queue.
    await downloader.process_queue.coro(downloader)

    downloader.download_next_song.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_file_quietly_swallows_os_error(downloader):
    with patch("cogs.utils.music.downloader.os.remove", side_effect=OSError("gone")):
        downloader._delete_file_quietly("missing/file.mp3")  # must not raise


@pytest.mark.asyncio
async def test_stop_cancels_running_process_queue_and_transitions_to_stopped(
    downloader, state
):
    downloader.queue = [("song", MagicMock(), False)]
    downloader.download_next_song = AsyncMock(side_effect=lambda: asyncio.sleep(10))
    downloader.process_queue.start()
    await asyncio.sleep(0)
    assert downloader.process_queue.is_running()

    await downloader.stop()

    assert downloader.queue == []
    assert downloader.queue_cancelled is True
    state.state_machine.transition_to.assert_called_once()
