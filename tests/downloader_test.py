import asyncio
import contextlib

import pytest
from unittest.mock import AsyncMock, MagicMock

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
