import pytest
from unittest.mock import AsyncMock, MagicMock

from cogs.utils.music.playlist import Playlist
from cogs.models.song import Song


@pytest.fixture
def state():
    state = MagicMock()
    state.player.join_voice_channel = AsyncMock()
    return state


@pytest.fixture
def playlist(state):
    return Playlist(state)


def make_song(title="song"):
    message = MagicMock()
    return Song("path", {"title": title}, message)


def test_empty_true_when_no_songs_and_not_looping(playlist):
    assert playlist.empty() is True


def test_empty_false_when_songs_queued(playlist):
    playlist.songs.append(make_song())
    assert playlist.empty() is False


def test_empty_false_when_looping_current_song_with_no_queue(playlist):
    # Regression: a single looped song with nothing else queued must not be
    # treated as "empty" (previously caused the state machine to disconnect
    # the bot instead of replaying the looped song).
    playlist.loop = True
    playlist.current_song = make_song()
    assert playlist.songs == []
    assert playlist.empty() is False


def test_empty_true_when_looping_but_no_current_song(playlist):
    playlist.loop = True
    playlist.current_song = None
    assert playlist.empty() is True


@pytest.mark.asyncio
async def test_get_next_returns_looped_song_and_resets_progress(playlist):
    song = make_song()
    song.current_seconds = 42
    playlist.loop = True
    playlist.current_song = song

    next_song = await playlist.get_next()

    assert next_song is song
    assert next_song.current_seconds == 0


@pytest.mark.asyncio
async def test_get_next_returns_none_when_queue_empty_and_not_looping(playlist):
    assert await playlist.get_next() is None


@pytest.mark.asyncio
async def test_get_next_pops_next_queued_song(playlist):
    first = make_song("first")
    second = make_song("second")
    playlist.songs = [first, second]

    next_song = await playlist.get_next()

    assert next_song is first
    assert playlist.songs == [second]
    assert playlist.current_song is first


def test_toggle_loop_flips_state_and_returns_label(playlist):
    assert playlist.toggle_loop() == "on"
    assert playlist.loop is True
    assert playlist.toggle_loop() == "off"
    assert playlist.loop is False


def test_toggle_shuffle_flips_state_and_returns_label(playlist):
    assert playlist.toggle_shuffle() == "on"
    assert playlist.shuffle is True
    assert playlist.toggle_shuffle() == "off"
    assert playlist.shuffle is False


@pytest.mark.asyncio
async def test_add_appends_song_and_joins_voice_channel(playlist, state):
    message = MagicMock()
    await playlist.add("path", {"title": "new song"}, message)

    state.player.join_voice_channel.assert_awaited_once_with(message)
    assert len(playlist.songs) == 1
    assert playlist.songs[0].title == "new song"


@pytest.mark.asyncio
async def test_clear_resets_songs_and_current_state(playlist):
    playlist.songs = [make_song()]
    playlist.current_song = make_song()
    playlist.last_song = make_song()

    await playlist.clear()

    assert playlist.songs == []
    assert playlist.current_song is None
    assert playlist.last_song is None


def test_get_embed_when_empty(playlist):
    embed = playlist.get_embed()
    assert embed.description == "The playlist is empty."


def test_get_embed_lists_queued_songs(playlist):
    playlist.songs = [make_song("Song One"), make_song("Song Two")]
    embed = playlist.get_embed()
    assert "Song One" in embed.description
    assert "Song Two" in embed.description
