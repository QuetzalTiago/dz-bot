import pytest
from unittest.mock import AsyncMock, MagicMock

from cogs.utils.music.playlist import Playlist
from cogs.models.song import Song


@pytest.fixture
def state():
    state = MagicMock()
    state.player.join_voice_channel = AsyncMock()
    state.downloader.queue = []
    return state


@pytest.fixture
def playlist(state):
    return Playlist(state)


def make_song(title="song"):
    message = MagicMock()
    return Song(
        "path", {"title": title, "original_url": f"http://example.com/{title}"}, message
    )


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
    result = await playlist.add("path", {"title": "new song"}, message)

    state.player.join_voice_channel.assert_awaited_once_with(message)
    assert len(playlist.songs) == 1
    assert playlist.songs[0].title == "new song"
    assert result is True


@pytest.mark.asyncio
async def test_add_drops_song_when_join_voice_channel_fails(playlist, state):
    # Regression test: if the bot couldn't join voice (requester left, missing
    # permission, etc.), the song must not be queued - otherwise the state
    # machine later crashes trying to play with no voice client. The caller
    # (downloader.download_next_song) relies on this return value to decide
    # whether to react success or send a failure instead.
    state.player.join_voice_channel = AsyncMock(return_value=None)
    message = MagicMock()

    result = await playlist.add("path", {"title": "new song"}, message)

    assert playlist.songs == []
    assert result is False


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


def test_get_embed_reports_songs_still_downloading_instead_of_empty(playlist, state):
    """Regression test: a song can finish downloading and start playing
    (moving it out of `songs` into `current_song`) while the rest of a
    Spotify playlist/album import are still in the download queue - that
    must not be reported as an empty playlist."""
    state.downloader.queue = [("song", MagicMock(), None), ("song2", MagicMock(), None)]
    embed = playlist.get_embed()
    assert "2" in embed.description
    assert "still downloading" in embed.description
    assert "empty" not in embed.description


def test_get_embed_lists_queued_songs(playlist):
    playlist.songs = [make_song("Song One"), make_song("Song Two")]
    embed = playlist.get_embed()
    assert "Song One" in embed.description
    assert "Song Two" in embed.description


def test_get_embed_notes_download_queue_alongside_queued_songs(playlist, state):
    state.downloader.queue = [("song", MagicMock(), None)]
    playlist.songs = [make_song("Song One")]
    embed = playlist.get_embed()
    assert "Song One" in embed.description
    assert "1** more in the download queue." in embed.description


def test_get_embed_lists_exactly_20_songs_without_and_more(playlist):
    # Regression test: with exactly 20 queued songs, the 20th must still be
    # listed and no spurious "and more..." should be appended.
    playlist.songs = [make_song(f"Song {i}") for i in range(1, 21)]
    embed = playlist.get_embed()
    assert "Song 20" in embed.description
    assert "and more..." not in embed.description


def test_get_embed_lists_more_than_20_songs_with_and_more(playlist):
    playlist.songs = [make_song(f"Song {i}") for i in range(1, 22)]
    embed = playlist.get_embed()
    assert "Song 20" in embed.description
    assert "Song 21" not in embed.description
    assert "and more..." in embed.description


@pytest.mark.asyncio
async def test_send_song_embed_reflects_loop_state(playlist):
    playlist.loop = True
    song = make_song("Looped Song")
    song.info["original_url"] = "http://example.com/looped"
    song.message.channel.send = AsyncMock(return_value=MagicMock())

    await playlist.send_song_embed(song)

    embed = song.message.channel.send.call_args.kwargs["embed"]
    assert any("Loop" in field.name or "Loop" in field.value for field in embed.fields)


@pytest.mark.asyncio
async def test_send_song_embed_returns_none_and_logs_on_send_failure(playlist):
    song = make_song("Doomed Song")
    song.message.channel.send = AsyncMock(side_effect=Exception("channel gone"))

    result = await playlist.send_song_embed(song)

    assert result is None
    assert song.embed_message is None


def test_handle_index_shuffle_picks_within_range(playlist, monkeypatch):
    playlist.shuffle = True
    playlist.songs = [make_song("a"), make_song("b"), make_song("c")]
    monkeypatch.setattr("cogs.utils.music.playlist.random.randint", lambda a, b: 2)

    assert playlist._handle_index() == 2


def test_handle_index_no_shuffle_or_empty_returns_zero(playlist):
    playlist.shuffle = False
    playlist.songs = [make_song("a")]
    assert playlist._handle_index() == 0

    playlist.shuffle = True
    playlist.songs = []
    assert playlist._handle_index() == 0


def test_set_last_song(playlist):
    song = make_song()
    playlist.set_last_song(song)
    assert playlist.last_song is song


@pytest.mark.asyncio
async def test_delete_song_log_deletes_all_messages_and_clears_list(playlist):
    song = make_song()
    msg1, msg2 = MagicMock(), MagicMock()
    msg1.delete = AsyncMock()
    msg2.delete = AsyncMock()
    song.messages_to_delete = [msg1, msg2]

    await playlist.delete_song_log(song)

    msg1.delete.assert_awaited_once()
    msg2.delete.assert_awaited_once()
    assert song.messages_to_delete == []


@pytest.mark.asyncio
async def test_delete_song_log_continues_past_delete_failure(playlist):
    song = make_song()
    ok_msg = MagicMock()
    ok_msg.delete = AsyncMock()
    failing_msg = MagicMock()
    failing_msg.delete = AsyncMock(side_effect=Exception("already deleted"))
    song.messages_to_delete = [failing_msg, ok_msg]

    await playlist.delete_song_log(song)  # must not raise

    ok_msg.delete.assert_awaited_once()
    assert song.messages_to_delete == []


@pytest.mark.asyncio
async def test_update_curr_song_message_noop_without_current_song(playlist):
    playlist.current_song = None
    await playlist.update_curr_song_message()  # must not raise


@pytest.mark.asyncio
async def test_update_curr_song_message_noop_without_embed_message(playlist):
    song = make_song()
    song.current_seconds = 0
    song.embed_message = None
    playlist.current_song = song

    await playlist.update_curr_song_message()

    assert song.current_seconds > 0


@pytest.mark.asyncio
async def test_update_curr_song_message_edits_existing_embed(playlist):
    song = make_song()
    song.current_seconds = 0
    song.embed_message = MagicMock()
    song.embed_message.edit = AsyncMock()
    playlist.current_song = song

    await playlist.update_curr_song_message()

    song.embed_message.edit.assert_awaited_once()
    assert "embed" in song.embed_message.edit.call_args.kwargs


@pytest.mark.asyncio
async def test_update_curr_song_message_swallows_edit_failure(playlist):
    song = make_song()
    song.embed_message = MagicMock()
    song.embed_message.edit = AsyncMock(side_effect=Exception("message gone"))
    playlist.current_song = song

    await playlist.update_curr_song_message()  # must not raise


@pytest.mark.asyncio
async def test_update_message_noop_without_sent_message(playlist):
    playlist.sent_message = None
    await playlist.update_message()  # must not raise


@pytest.mark.asyncio
async def test_update_message_edits_sent_message_with_current_embed(playlist):
    playlist.sent_message = MagicMock()
    playlist.sent_message.edit = AsyncMock()
    playlist.songs = [make_song("Queued")]

    await playlist.update_message()

    playlist.sent_message.edit.assert_awaited_once()
    embed = playlist.sent_message.edit.call_args.kwargs["embed"]
    assert "Queued" in embed.description


@pytest.mark.asyncio
async def test_update_message_swallows_edit_failure(playlist):
    playlist.sent_message = MagicMock()
    playlist.sent_message.edit = AsyncMock(side_effect=Exception("message gone"))

    await playlist.update_message()  # must not raise
