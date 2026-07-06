import os

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.music import Music
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
