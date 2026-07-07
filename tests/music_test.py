import asyncio
import os

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.music import Music, delete_file, setup
from cogs.utils.emojis import DONE, ERROR
from cogs.utils.music.state_machine import State
from tests.mocks import mock_ctx


@pytest.fixture
def config():
    return {
        "prefix": "!",
        "secrets": {
            "spotifyClientId": "test",
            "spotifyClientSecret": "test",
            "geniusApiKey": "test",
        },
        "max_playlist_size": 100,
    }


@pytest_asyncio.fixture
async def bot(config):
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix=config["prefix"], intents=intents)
    await bot._async_setup_hook()
    return bot


@pytest_asyncio.fixture
async def music_cog(bot, config):
    cog = Music(bot, config)
    await bot.add_cog(cog)
    return cog


def state_for(music_cog, ctx):
    return music_cog.get_state(ctx.guild)


async def call(cmd, cog, ctx, **kwargs):
    """Invoke a hybrid command's callback directly, bypassing checks."""
    await cmd.callback(cog, ctx, **kwargs)


# ---- play ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_play_user_not_connected(music_cog, bot):
    ctx = mock_ctx(bot)
    ctx.author.voice = None
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.play, music_cog, ctx, query="song")
        ctx.send.assert_awaited_with("You are not connected to a voice channel!")
        fail.assert_awaited()


@pytest.mark.asyncio
async def test_play_playlist_max_size(music_cog, bot):
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()
    state = state_for(music_cog, ctx)
    state.downloader.queue = [MagicMock()] * 50
    state.playlist.songs = [MagicMock()] * 50
    state.playlist.max_size = 100
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.play, music_cog, ctx, query="song")
        ctx.send.assert_awaited_with(
            "Maximum playlist size reached. Please *skip* the current song "
            "or *clear* the list to add more."
        )
        fail.assert_awaited()


@pytest.mark.asyncio
async def test_play_missing_url(music_cog, bot):
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()
    ctx.message.content = "!play"
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.play, music_cog, ctx, query="")
        ctx.send.assert_awaited_with(
            "Missing URL use command like: play "
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        fail.assert_awaited()


@pytest.mark.asyncio
async def test_play_youtube_playlist(music_cog, bot):
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()
    url = "https://www.youtube.com/playlist?list=PL123456789"
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.play, music_cog, ctx, query=url)
        ctx.send.assert_awaited_with(
            "Youtube playlists not yet supported. Try a spotify link instead."
        )
        fail.assert_awaited()


@pytest.mark.asyncio
async def test_play_single_video_with_list_param_is_not_rejected(music_cog, bot):
    # Regression test: a single-video share link can carry a "list=" param
    # (watch-later, mix/radio, up-next queue) without being a real playlist
    # request - it must still be queued as that one video.
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RD123456789"
    state = music_cog._state_for_ctx(ctx)
    state.downloader.enqueue = AsyncMock()
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.play, music_cog, ctx, query=url)
        state.downloader.enqueue.assert_awaited_once_with(url, ctx.message)
        fail.assert_not_awaited()


@pytest.mark.asyncio
async def test_play_success(music_cog, bot):
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()
    song_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    state = state_for(music_cog, ctx)
    with patch.object(
        state.downloader, "enqueue", new_callable=AsyncMock
    ) as mock_enqueue:
        await call(music_cog.play, music_cog, ctx, query=song_url)
        mock_enqueue.assert_awaited_with(song_url, ctx.message)


@pytest.mark.asyncio
async def test_play_enqueue_failure_reports_error(music_cog, bot):
    # A bad Spotify URL (or any enqueue failure) must not blow up as an
    # uncaught exception - it should surface like every other command error.
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()
    song_url = "https://open.spotify.com/track/doesnotexist"
    state = state_for(music_cog, ctx)
    with patch.object(
        state.downloader, "enqueue", new_callable=AsyncMock
    ) as mock_enqueue, patch.object(
        music_cog, "cog_failure", new_callable=AsyncMock
    ) as fail:
        mock_enqueue.side_effect = Exception("spotify blew up")
        await call(music_cog.play, music_cog, ctx, query=song_url)
        ctx.send.assert_awaited_with(
            "Something went wrong queueing that song. Check the URL and try again."
        )
        fail.assert_awaited()


# ---- pause / resume ------------------------------------------------------

@pytest.mark.asyncio
async def test_pause_playing(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    state.state_machine.get_state = MagicMock(return_value=State.PLAYING)
    state.state_machine.transition_to = MagicMock()
    with patch.object(music_cog, "cog_success", new_callable=AsyncMock) as ok:
        await call(music_cog.pause, music_cog, ctx)
        state.state_machine.transition_to.assert_called_with(State.PAUSED)
        ok.assert_awaited_with(ctx.message)


@pytest.mark.asyncio
async def test_pause_not_playing(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    state.state_machine.get_state = MagicMock(return_value=State.STOPPED)
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.pause, music_cog, ctx)
        ctx.send.assert_awaited_with("DJ Khaled is not playing anything!")
        fail.assert_awaited()


@pytest.mark.asyncio
async def test_resume_paused(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    state.state_machine.get_state = MagicMock(return_value=State.PAUSED)
    state.state_machine.transition_to = MagicMock()
    with patch.object(music_cog, "cog_success", new_callable=AsyncMock) as ok:
        await call(music_cog.resume, music_cog, ctx)
        state.state_machine.transition_to.assert_called_with(State.RESUMED)
        ok.assert_awaited_with(ctx.message)


@pytest.mark.asyncio
async def test_resume_not_paused(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    state.state_machine.get_state = MagicMock(return_value=State.STOPPED)
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.resume, music_cog, ctx)
        ctx.send.assert_awaited_with("DJ Khaled is not paused!")
        fail.assert_awaited()


# ---- lyrics --------------------------------------------------------------

@pytest.mark.asyncio
async def test_lyrics_no_song(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    state.playlist.current_song = None
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.lyrics, music_cog, ctx)
        ctx.message.channel.send.assert_awaited_with(
            "DJ Khaled is not playing anything! Play a spotify url to get lyrics."
        )
        fail.assert_awaited()


@pytest.mark.asyncio
async def test_lyrics_success_writes_unique_file_and_cleans_up(music_cog, bot, tmp_path):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    song = MagicMock()
    song.lyrics = "some lyrics"
    song.title = "Sample Song"
    song.message = MagicMock()
    song.message.channel = ctx.channel
    song.messages_to_delete = []
    state.playlist.current_song = song

    written_names = []
    real_open = open

    def tracking_open(path, *args, **kwargs):
        written_names.append(path)
        return real_open(os.path.join(tmp_path, os.path.basename(path)), *args, **kwargs)

    with patch.object(
        music_cog, "cog_success", new_callable=AsyncMock
    ) as ok, patch.object(
        music_cog, "send_lyrics_file", new_callable=AsyncMock
    ) as send_file, patch("cogs.music.open", side_effect=tracking_open), patch(
        "cogs.music.os.path.exists", return_value=True
    ), patch("cogs.music.os.remove") as mock_remove:
        await call(music_cog.lyrics, music_cog, ctx)

    assert written_names[0] != "lyrics.txt"  # unique per-invocation filename
    send_file.assert_awaited_once_with(song.message.channel, written_names[0])
    mock_remove.assert_called_once_with(written_names[0])
    ok.assert_awaited_with(ctx.message)
    assert ctx.message in song.messages_to_delete


@pytest.mark.asyncio
async def test_lyrics_no_lyrics(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    song = MagicMock()
    song.lyrics = None
    song.title = "Sample Song"
    song.message = MagicMock()
    song.message.channel = ctx.channel
    state.playlist.current_song = song
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.lyrics, music_cog, ctx)
        song.message.channel.send.assert_awaited_with(
            f"No lyrics available for **{song.title}**. "
            "Try using a spotify link instead."
        )
        fail.assert_awaited()


# ---- skip ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_skip_song_not_playing(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    state.state_machine.get_state = MagicMock(return_value=State.STOPPED)
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.skip_song, music_cog, ctx)
        ctx.send.assert_awaited_with("DJ Khaled is not playing anything!")
        fail.assert_awaited()


@pytest.mark.asyncio
async def test_skip_song_loop_enabled(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    state.state_machine.get_state = MagicMock(return_value=State.PLAYING)
    state.playlist.loop = True
    with patch.object(music_cog, "cog_failure", new_callable=AsyncMock) as fail:
        await call(music_cog.skip_song, music_cog, ctx)
        ctx.message.channel.send.assert_awaited_with(
            "*Loop* is **ON**. Please disable *Loop* before skipping."
        )
        fail.assert_awaited()


@pytest.mark.asyncio
async def test_skip_song_success(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    state.state_machine.get_state = MagicMock(return_value=State.PLAYING)
    state.playlist.loop = False
    with patch.object(state.player, "skip", new_callable=AsyncMock) as mock_skip:
        await call(music_cog.skip_song, music_cog, ctx)
        mock_skip.assert_awaited_with(ctx.message)


# ---- stop / clear --------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_command(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    with patch.object(state.state_machine, "stop", new_callable=AsyncMock) as sm_stop, \
         patch.object(state.downloader, "stop", new_callable=AsyncMock) as dl_stop, \
         patch.object(state.player, "stop", new_callable=AsyncMock) as p_stop, \
         patch.object(music_cog, "_clear_state", new_callable=AsyncMock) as clear, \
         patch.object(music_cog, "cog_success", new_callable=AsyncMock) as ok:
        await call(music_cog.stop, music_cog, ctx)
        sm_stop.assert_awaited()
        dl_stop.assert_awaited()
        p_stop.assert_awaited()
        clear.assert_awaited_with(state)
        ok.assert_awaited_with(ctx.message)
        ctx.message.delete.assert_awaited()


@pytest.mark.asyncio
async def test_stop_command_survives_already_deleted_invocation(music_cog, bot):
    # Regression test: `ctx.message` is synthetic for slash-command
    # invocations (discord.py can't delete it) and may already be gone (a
    # concurrent purge, manual deletion, double-invocation) - either raises
    # discord.NotFound, which must not surface as a command failure.
    ctx = mock_ctx(bot)
    ctx.message.delete = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Unknown Message"))
    state = state_for(music_cog, ctx)
    with patch.object(state.state_machine, "stop", new_callable=AsyncMock), \
         patch.object(state.downloader, "stop", new_callable=AsyncMock), \
         patch.object(state.player, "stop", new_callable=AsyncMock), \
         patch.object(music_cog, "_clear_state", new_callable=AsyncMock), \
         patch.object(music_cog, "cog_success", new_callable=AsyncMock):
        await call(music_cog.stop, music_cog, ctx)  # must not raise


@pytest.mark.asyncio
async def test_clear_command(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    with patch.object(state.downloader, "clear", new_callable=AsyncMock) as dl_clear, \
         patch.object(state.playlist, "clear", new_callable=AsyncMock) as pl_clear, \
         patch.object(music_cog, "cog_success", new_callable=AsyncMock) as ok:
        await call(music_cog.clear, music_cog, ctx)
        dl_clear.assert_awaited()
        pl_clear.assert_awaited()
        ctx.send.assert_awaited_with("The playlist has been cleared!")
        ok.assert_awaited_with(ctx.message)
        ctx.message.delete.assert_awaited()


# ---- loop / shuffle ------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_command(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    with patch.object(state.playlist, "toggle_loop", return_value="on"), \
         patch.object(music_cog, "cog_success", new_callable=AsyncMock) as ok:
        await call(music_cog.loop, music_cog, ctx)
        ctx.send.assert_awaited_with("Loop is now **on**.")
        ok.assert_awaited_with(ctx.message)


@pytest.mark.asyncio
async def test_shuffle_command(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    with patch.object(state.playlist, "toggle_shuffle", return_value="on"), \
         patch.object(music_cog, "cog_success", new_callable=AsyncMock) as ok:
        await call(music_cog.shuffle, music_cog, ctx)
        ctx.send.assert_awaited_with("Shuffle is now **on**.")
        ok.assert_awaited_with(ctx.message)


# ---- playlist ------------------------------------------------------------

@pytest.mark.asyncio
async def test_playlist_command(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    playlist_embed = discord.Embed(title="Playlist")
    with patch.object(state.playlist, "get_embed", return_value=playlist_embed):
        await call(music_cog._playlist, music_cog, ctx)
        ctx.send.assert_awaited_with(embed=playlist_embed)
        assert state.playlist.sent_message is not None
        assert state.playlist.user_req_message == ctx.message


# ---- most_played / most_requested -----------------------------------------

def test_most_played_and_most_requested_have_no_multiword_aliases(music_cog):
    # Regression test: discord.py's prefix-command parser only ever extracts
    # a single whitespace-delimited word as invoked_with, so a multi-word
    # alias like "top users" is never routed to its own command - it's parsed
    # as "top" (an alias of the *other* command, most_played), silently
    # invoking the wrong command instead of just being unreachable. Same bug
    # class already fixed once in chess_leaderboard.py.
    for alias in music_cog.most_played.aliases:
        assert " " not in alias
    for alias in music_cog.most_requested.aliases:
        assert " " not in alias


@pytest.mark.asyncio
async def test_most_played_without_database(music_cog, bot):
    ctx = mock_ctx(bot)
    with patch.object(bot, "get_cog", return_value=None):
        await call(music_cog.most_played, music_cog, ctx)
    ctx.send.assert_awaited_once_with("Most played songs are temporarily unavailable.")


@pytest.mark.asyncio
async def test_most_played_with_database_builds_embed(music_cog, bot):
    ctx = mock_ctx(bot)
    db = MagicMock()
    db.get_most_played_songs = AsyncMock(
        return_value=[("http://example.com/a", "Song A", 3)]
    )
    with patch.object(bot, "get_cog", return_value=db):
        await call(music_cog.most_played, music_cog, ctx)

    embed = ctx.send.call_args.kwargs["embed"]
    assert embed.title == "Top 5 Most Played Songs 🎵"
    assert "[Song A](http://example.com/a)" in embed.fields[0].value
    assert "3" in embed.fields[0].value
    # Regression test: this command used to never clear/replace the ACK
    # reaction added by bot.py's before_invoke hook on success, leaving it
    # stuck forever unlike every sibling music command.
    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_awaited_once_with("✅")


@pytest.mark.asyncio
async def test_most_played_reports_error_when_db_raises(music_cog, bot):
    ctx = mock_ctx(bot)
    db = MagicMock()
    db.get_most_played_songs = AsyncMock(side_effect=RuntimeError("db down"))
    with patch.object(bot, "get_cog", return_value=db):
        await call(music_cog.most_played, music_cog, ctx)

    ctx.send.assert_awaited_once_with(
        "Something went wrong fetching the most played songs."
    )
    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_awaited_once_with("❌")


@pytest.mark.asyncio
async def test_most_requested_without_database(music_cog, bot):
    ctx = mock_ctx(bot)
    with patch.object(bot, "get_cog", return_value=None):
        await call(music_cog.most_requested, music_cog, ctx)
    ctx.send.assert_awaited_once_with(
        "Most requested songs are temporarily unavailable."
    )


@pytest.mark.asyncio
async def test_most_requested_with_database_builds_embed(music_cog, bot):
    ctx = mock_ctx(bot)
    db = MagicMock()
    db.get_most_song_requests = AsyncMock(return_value=[(42, 7)])
    with patch.object(bot, "get_cog", return_value=db):
        await call(music_cog.most_requested, music_cog, ctx)

    embed = ctx.send.call_args.kwargs["embed"]
    assert embed.title == "Top 5 users with most requested songs 🎵"
    assert "<@42>" in embed.fields[0].value
    assert "7" in embed.fields[0].value
    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_awaited_once_with("✅")


@pytest.mark.asyncio
async def test_most_requested_reports_error_when_db_raises(music_cog, bot):
    ctx = mock_ctx(bot)
    db = MagicMock()
    db.get_most_song_requests = AsyncMock(side_effect=RuntimeError("db down"))
    with patch.object(bot, "get_cog", return_value=db):
        await call(music_cog.most_requested, music_cog, ctx)

    ctx.send.assert_awaited_once_with(
        "Something went wrong fetching the most requested songs."
    )
    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_awaited_once_with("❌")


# ---- per-guild isolation -------------------------------------------------

@pytest.mark.asyncio
async def test_states_are_per_guild(music_cog, bot):
    guild_a = MagicMock(spec=discord.Guild)
    guild_a.id = 1
    guild_b = MagicMock(spec=discord.Guild)
    guild_b.id = 2
    state_a = music_cog.get_state(guild_a)
    state_b = music_cog.get_state(guild_b)
    assert state_a is not state_b
    assert music_cog.get_state(guild_a) is state_a


@pytest.mark.asyncio
async def test_cleanup_files_does_not_delete_other_guilds_active_song(
    music_cog, bot, tmp_path
):
    # Regression test: DOWNLOAD_DIR is shared by every guild, so cleanup
    # triggered by guild A must not delete a file that guild B is actively
    # using (playing or queued), even though guild A's cleanup call only
    # knows about its own current song/queue.
    guild_b = MagicMock(spec=discord.Guild)
    guild_b.id = 2
    state_b = music_cog.get_state(guild_b)

    song_a_path = str(tmp_path / "song_a.mp3")
    song_b_path = str(tmp_path / "song_b.mp3")
    stale_path = str(tmp_path / "stale.mp3")
    for path in (song_a_path, song_b_path, stale_path):
        open(path, "w").close()

    song_a = MagicMock()
    song_a.path = song_a_path
    song_b = MagicMock()
    song_b.path = song_b_path
    state_b.playlist.current_song = song_b

    with patch("cogs.music.DOWNLOAD_DIR", str(tmp_path)):
        music_cog.cleanup_files(song_a, [])

    assert os.path.exists(song_a_path)
    assert os.path.exists(song_b_path)
    assert not os.path.exists(stale_path)


@pytest.mark.asyncio
async def test_cleanup_files_does_not_delete_pending_download(music_cog, bot, tmp_path):
    # Regression test: a file can finish downloading before it's appended to
    # any guild's playlist (e.g. a Spotify-sourced request still awaiting
    # lyrics in Downloader.download_next_song()). Another guild's cleanup
    # triggered in that window must not delete it.
    song_a = MagicMock()
    song_a.path = str(tmp_path / "song_a.mp3")
    pending_path = str(tmp_path / "pending.mp3")
    for path in (song_a.path, pending_path):
        open(path, "w").close()

    music_cog.pending_download_paths.add(pending_path)

    with patch("cogs.music.DOWNLOAD_DIR", str(tmp_path)):
        music_cog.cleanup_files(song_a, [])

    assert os.path.exists(pending_path)


@pytest.mark.asyncio
async def test_cleanup_files_noop_when_download_dir_missing(music_cog, tmp_path):
    missing_dir = str(tmp_path / "does-not-exist")
    with patch("cogs.music.DOWNLOAD_DIR", missing_dir):
        # Must not raise even though os.listdir(missing_dir) would.
        music_cog.cleanup_files(MagicMock(path="x"), [])


# ---- handle_forced_disconnect ---------------------------------------------

@pytest.mark.asyncio
async def test_handle_forced_disconnect_tears_down_existing_state(music_cog):
    guild = MagicMock(spec=discord.Guild)
    guild.id = 42
    guild.voice_client = None
    state = music_cog.get_state(guild)
    state.teardown = AsyncMock()

    await music_cog.handle_forced_disconnect(guild)

    state.teardown.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_forced_disconnect_noop_when_no_state_for_guild(music_cog):
    guild = MagicMock(spec=discord.Guild)
    guild.id = 999
    guild.voice_client = None
    # No prior get_state call for this guild id; must not raise or create one.
    await music_cog.handle_forced_disconnect(guild)
    assert guild.id not in music_cog.guild_states


@pytest.mark.asyncio
async def test_handle_forced_disconnect_skips_teardown_when_already_reconnected(
    music_cog,
):
    """Regression test: a stale disconnect event for an old session must not
    tear down a brand-new one that reconnected before the event arrived."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 42
    # The guild already has a live voice client by the time this handler
    # runs - a fast `!play` won the race against the delayed gateway event.
    guild.voice_client = MagicMock()
    state = music_cog.get_state(guild)
    state.teardown = AsyncMock()

    await music_cog.handle_forced_disconnect(guild)

    state.teardown.assert_not_awaited()


# ---- cog_success / cog_failure (real behavior, not mocked) ----------------

@pytest.mark.asyncio
async def test_cog_success_clears_reactions_and_adds_done(music_cog):
    message = MagicMock()
    message.clear_reactions = AsyncMock()
    message.add_reaction = AsyncMock()

    await music_cog.cog_success(message)

    message.clear_reactions.assert_awaited_once()
    message.add_reaction.assert_awaited_once_with(DONE)


@pytest.mark.asyncio
async def test_cog_success_swallows_discord_exception(music_cog):
    message = MagicMock()
    message.clear_reactions = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "boom"))
    message.add_reaction = AsyncMock()

    await music_cog.cog_success(message)  # must not raise


@pytest.mark.asyncio
async def test_cog_failure_marks_error_and_schedules_deletion(music_cog):
    sent_message = MagicMock()
    sent_message.delete = AsyncMock()
    query_message = MagicMock()
    query_message.clear_reactions = AsyncMock()
    query_message.add_reaction = AsyncMock()
    query_message.delete = AsyncMock()

    real_create_task = music_cog.bot.loop.create_task
    created = []

    def capture(coro):
        task = real_create_task(coro)
        created.append(task)
        return task

    with patch.object(music_cog.bot.loop, "create_task", side_effect=capture), \
            patch("cogs.music.asyncio.sleep", new=AsyncMock()):
        await music_cog.cog_failure(sent_message, query_message)
        await asyncio.gather(*created)

    query_message.clear_reactions.assert_awaited_once()
    query_message.add_reaction.assert_awaited_once_with(ERROR)
    sent_message.delete.assert_awaited_once()
    query_message.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_cog_failure_swallows_discord_exception_on_reaction(music_cog):
    sent_message = MagicMock()
    query_message = MagicMock()
    query_message.clear_reactions = AsyncMock(
        side_effect=discord.HTTPException(MagicMock(), "boom")
    )
    query_message.add_reaction = AsyncMock()

    with patch.object(
        music_cog.bot.loop, "create_task", side_effect=lambda coro: coro.close()
    ):
        await music_cog.cog_failure(sent_message, query_message)  # must not raise


@pytest.mark.asyncio
async def test_cog_failure_delete_error_log_swallows_deletion_errors(music_cog):
    # delete_error_log's own try/except must swallow a failure to delete
    # (e.g. one of the messages was already removed) rather than letting it
    # escape the scheduled task.
    sent_message = MagicMock()
    sent_message.delete = AsyncMock(side_effect=discord.NotFound(MagicMock(), "gone"))
    query_message = MagicMock()
    query_message.clear_reactions = AsyncMock()
    query_message.add_reaction = AsyncMock()
    query_message.delete = AsyncMock()

    real_create_task = music_cog.bot.loop.create_task
    created = []

    def capture(coro):
        task = real_create_task(coro)
        created.append(task)
        return task

    with patch.object(music_cog.bot.loop, "create_task", side_effect=capture), \
            patch("cogs.music.asyncio.sleep", new=AsyncMock()):
        await music_cog.cog_failure(sent_message, query_message)
        await asyncio.gather(*created)  # must not raise despite the NotFound


# ---- send_lyrics_file ------------------------------------------------------

@pytest.mark.asyncio
async def test_send_lyrics_file_sends_file_contents(music_cog, tmp_path):
    lyrics_path = tmp_path / "lyrics.txt"
    lyrics_path.write_text("some lyrics")
    channel = MagicMock()
    channel.send = AsyncMock(return_value="sent")

    result = await music_cog.send_lyrics_file(channel, str(lyrics_path))

    assert result == "sent"
    channel.send.assert_awaited_once()
    kwargs = channel.send.await_args.kwargs
    assert isinstance(kwargs["file"], discord.File)


# ---- _extract_query ---------------------------------------------------------

def test_extract_query_prefers_parsed_argument(music_cog):
    ctx = MagicMock()
    ctx.message.content = "!play some other song"
    assert music_cog._extract_query(ctx, "given query") == "given query"


def test_extract_query_falls_back_to_slicing_prefix_command_content(music_cog):
    ctx = MagicMock()
    ctx.message.content = "!play my favorite song"
    assert music_cog._extract_query(ctx, "") == "my favorite song"


def test_extract_query_falls_back_to_slicing_short_alias(music_cog):
    ctx = MagicMock()
    ctx.message.content = "!p my favorite song"
    assert music_cog._extract_query(ctx, "") == "my favorite song"


def test_extract_query_returns_empty_when_no_match(music_cog):
    ctx = MagicMock()
    ctx.message.content = "!stop"
    assert music_cog._extract_query(ctx, "") == ""


def test_extract_query_matches_uppercase_prefix_case_insensitively(music_cog):
    """Regression test: a mixed/upper-case configured prefix (e.g. "DZ!")
    must still match the lower-cased message content, not just lower-case
    prefixes like the default "!"."""
    music_cog.config["prefix"] = "DZ!"
    ctx = MagicMock()
    ctx.message.content = "DZ!play my favorite song"
    assert music_cog._extract_query(ctx, "") == "my favorite song"


# ---- _playlist deletes previous tracking messages --------------------------

@pytest.mark.asyncio
async def test_playlist_deletes_previous_sent_and_request_messages(music_cog, bot):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    old_sent = MagicMock()
    old_sent.delete = AsyncMock()
    old_req = MagicMock()
    old_req.delete = AsyncMock()
    state.playlist.sent_message = old_sent
    state.playlist.user_req_message = old_req

    with patch.object(music_cog, "cog_success", new_callable=AsyncMock):
        await call(music_cog._playlist, music_cog, ctx)

    old_sent.delete.assert_awaited_once()
    old_req.delete.assert_awaited_once()
    assert state.playlist.sent_message is ctx.send.return_value
    assert state.playlist.user_req_message is ctx.message


@pytest.mark.asyncio
async def test_playlist_swallows_discord_exception_deleting_previous_messages(
    music_cog, bot
):
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    old_sent = MagicMock()
    old_sent.delete = AsyncMock(side_effect=discord.NotFound(MagicMock(), "gone"))
    state.playlist.sent_message = old_sent
    state.playlist.user_req_message = None

    with patch.object(music_cog, "cog_success", new_callable=AsyncMock):
        await call(music_cog._playlist, music_cog, ctx)  # must not raise


@pytest.mark.asyncio
async def test_playlist_deletes_request_message_even_if_sent_message_delete_fails(
    music_cog, bot
):
    # Regression test: the two deletes used to share one try/except, so a
    # NotFound on the first (already-removed sent_message) skipped the
    # second delete entirely, leaking the old invocation message forever.
    ctx = mock_ctx(bot)
    state = state_for(music_cog, ctx)
    old_sent = MagicMock()
    old_sent.delete = AsyncMock(side_effect=discord.NotFound(MagicMock(), "gone"))
    old_req = MagicMock()
    old_req.delete = AsyncMock()
    state.playlist.sent_message = old_sent
    state.playlist.user_req_message = old_req

    with patch.object(music_cog, "cog_success", new_callable=AsyncMock):
        await call(music_cog._playlist, music_cog, ctx)

    old_req.delete.assert_awaited_once()


# ---- delete_file / setup module-level helpers ------------------------------

def test_delete_file_removes_existing_file(tmp_path):
    logger = MagicMock()
    path = tmp_path / "song.mp3"
    path.write_text("data")

    delete_file(str(path), logger)

    assert not path.exists()
    logger.info.assert_called_once()


def test_delete_file_logs_error_when_removal_fails(tmp_path):
    logger = MagicMock()
    missing_path = str(tmp_path / "does-not-exist.mp3")

    delete_file(missing_path, logger)  # must not raise

    logger.info.assert_called_once()
    assert "Error deleting file" in logger.info.call_args.args[0]


@pytest.mark.asyncio
async def test_setup_adds_music_cog(bot):
    with patch("cogs.music.load_config", return_value={"prefix": "!", "secrets": {}}):
        await setup(bot)
    assert bot.get_cog("Music") is not None
