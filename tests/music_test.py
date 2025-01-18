import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from discord.ext import commands
import discord

# Import the Music cog class and necessary modules
from cogs.music import Music
from cogs.utils.music.state_machine import State
from tests.mocks import mock_ctx

# Fixtures
@pytest.fixture
def config():
    return {
        "prefix": "!",  # Set the command prefix as per your configuration
        "secrets": {
            "spotifyClientId": "test",
            "spotifyClientSecret": "test",
            "geniusApiKey": "test",
            "other": "test",
            # Add all other necessary secret keys here
        },
        # Add other configuration keys used in your code
        "max_playlist_size": 100,
    }


@pytest_asyncio.fixture
async def bot(event_loop, config):
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix=config["prefix"], intents=intents, loop=event_loop)
    await bot._async_setup_hook()
    return bot


@pytest_asyncio.fixture
async def music_cog(bot, config):
    # Initialize the Music cog with the bot and configuration
    cog = Music(bot, config)
    await bot.add_cog(cog)
    return cog



# Tests for the 'play' command
@pytest.mark.asyncio
async def test_play_user_not_connected(music_cog, bot):
    """Test the 'play' command when the user is not connected to a voice channel."""
    ctx = mock_ctx(bot)
    ctx.author.voice = None  # User is not connected

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.play(ctx)

        ctx.send.assert_awaited_with("You are not connected to a voice channel!")
        mock_cog_failure.assert_awaited()


@pytest.mark.asyncio
async def test_play_playlist_max_size(music_cog, bot):
    """Test the 'play' command when the playlist is at maximum size."""
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()  # User is connected
    ctx.message.content = '!play some_song_url'

    # Mock playlist size
    music_cog.downloader.queue = [MagicMock()] * 50
    music_cog.playlist.songs = [MagicMock()] * 50
    music_cog.playlist.max_size = 100

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.play(ctx)

        ctx.send.assert_awaited_with(
            "Maximum playlist size reached. Please *skip* the current song or *clear* the list to add more."
        )
        mock_cog_failure.assert_awaited()


@pytest.mark.asyncio
async def test_play_missing_url(music_cog, bot):
    """Test the 'play' command when the song URL is missing."""
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()
    ctx.message.content = '!play'  # Missing URL

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.play(ctx)

        ctx.send.assert_awaited_with(
            "Missing URL use command like: play https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        mock_cog_failure.assert_awaited()


@pytest.mark.asyncio
async def test_play_youtube_playlist(music_cog, bot):
    """Test the 'play' command with a YouTube playlist URL."""
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()
    ctx.message.content = '!play https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123456789'

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.play(ctx)

        ctx.send.assert_awaited_with(
            "Youtube playlists not yet supported. Try a spotify link instead."
        )
        mock_cog_failure.assert_awaited()


@pytest.mark.asyncio
async def test_play_success(music_cog, bot):
    """Test the 'play' command with a valid song URL."""
    ctx = mock_ctx(bot)
    ctx.author.voice = MagicMock()
    song_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    ctx.message.content = f'!play {song_url}'

    with patch.object(music_cog.downloader, 'enqueue', new_callable=AsyncMock) as mock_enqueue:
        await music_cog.play(ctx)

        mock_enqueue.assert_awaited_with(song_url, ctx.message)


# Tests for the 'pause' command
@pytest.mark.asyncio
async def test_pause_playing(music_cog, bot):
    """Test the 'pause' command when music is playing."""
    ctx = mock_ctx(bot)

    music_cog.state_machine.get_state = MagicMock(return_value=State.PLAYING)
    music_cog.state_machine.transition_to = MagicMock()

    with patch.object(music_cog, 'cog_success', new_callable=AsyncMock) as mock_cog_success:
        await music_cog.pause(ctx)

        music_cog.state_machine.transition_to.assert_called_with(State.PAUSED)
        mock_cog_success.assert_awaited_with(ctx.message)


@pytest.mark.asyncio
async def test_pause_not_playing(music_cog, bot):
    """Test the 'pause' command when music is not playing."""
    ctx = mock_ctx(bot)

    music_cog.state_machine.get_state = MagicMock(return_value=State.STOPPED)

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.pause(ctx)

        ctx.send.assert_awaited_with("DJ Khaled is not playing anything!")
        mock_cog_failure.assert_awaited()


# Tests for the 'resume' command
@pytest.mark.asyncio
async def test_resume_paused(music_cog, bot):
    """Test the 'resume' command when music is paused."""
    ctx = mock_ctx(bot)

    music_cog.state_machine.get_state = MagicMock(return_value=State.PAUSED)
    music_cog.state_machine.transition_to = MagicMock()

    with patch.object(music_cog, 'cog_success', new_callable=AsyncMock) as mock_cog_success:
        await music_cog.resume(ctx)

        music_cog.state_machine.transition_to.assert_called_with(State.RESUMED)
        mock_cog_success.assert_awaited_with(ctx.message)


@pytest.mark.asyncio
async def test_resume_not_paused(music_cog, bot):
    """Test the 'resume' command when music is not paused."""
    ctx = mock_ctx(bot)

    music_cog.state_machine.get_state = MagicMock(return_value=State.STOPPED)

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.resume(ctx)

        ctx.send.assert_awaited_with("DJ Khaled is not paused!")
        mock_cog_failure.assert_awaited()


# Tests for the 'lyrics' command
@pytest.mark.asyncio
async def test_lyrics_no_song(music_cog, bot):
    """Test the 'lyrics' command when no song is playing."""
    ctx = mock_ctx(bot)
    music_cog.playlist.current_song = None

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.lyrics(ctx)

        ctx.message.channel.send.assert_awaited_with(
            "DJ Khaled is not playing anything! Play a spotify url to get lyrics."
        )
        mock_cog_failure.assert_awaited()


@pytest.mark.asyncio
async def test_lyrics_with_lyrics(music_cog, bot):
    """Test the 'lyrics' command when lyrics are available."""
    ctx = mock_ctx(bot)

    # Mock the current song with lyrics
    song = MagicMock()
    song.lyrics = "Sample lyrics"
    song.title = "Sample Song"
    song.message = MagicMock()
    song.message.channel = ctx.channel
    song.messages_to_delete = []

    music_cog.playlist.current_song = song

    with patch.object(music_cog, 'send_lyrics_file', new_callable=AsyncMock) as mock_send_lyrics_file, \
         patch('builtins.open', new_callable=MagicMock), \
         patch('os.remove', new_callable=MagicMock) as mock_os_remove, \
         patch.object(music_cog, 'cog_success', new_callable=AsyncMock) as mock_cog_success:

        mock_lyrics_message = MagicMock()
        mock_send_lyrics_file.return_value = mock_lyrics_message

        await music_cog.lyrics(ctx)

        mock_send_lyrics_file.assert_awaited_with(ctx.channel, 'lyrics.txt')
        mock_os_remove.assert_called_with('lyrics.txt')
        assert song.messages_to_delete == [mock_lyrics_message, ctx.message]
        mock_cog_success.assert_awaited_with(ctx.message)


@pytest.mark.asyncio
async def test_lyrics_no_lyrics(music_cog, bot):
    """Test the 'lyrics' command when lyrics are not available."""
    ctx = mock_ctx(bot)

    # Mock the current song without lyrics
    song = MagicMock()
    song.lyrics = None
    song.title = "Sample Song"
    song.message = MagicMock()
    song.message.channel = ctx.channel

    music_cog.playlist.current_song = song

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.lyrics(ctx)

        song.message.channel.send.assert_awaited_with(
            f"No lyrics available for **{song.title}**. Try using a spotify link instead."
        )
        mock_cog_failure.assert_awaited()


# Tests for the 'skip_song' command
@pytest.mark.asyncio
async def test_skip_song_not_playing(music_cog, bot):
    """Test the 'skip_song' command when nothing is playing."""
    ctx = mock_ctx(bot)
    music_cog.state_machine.get_state = MagicMock(return_value=State.STOPPED)

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.skip_song(ctx)

        ctx.send.assert_awaited_with("DJ Khaled is not playing anything!")
        mock_cog_failure.assert_awaited()


@pytest.mark.asyncio
async def test_skip_song_loop_enabled(music_cog, bot):
    """Test the 'skip_song' command when loop is enabled."""
    ctx = mock_ctx(bot)
    music_cog.state_machine.get_state = MagicMock(return_value=State.PLAYING)
    music_cog.playlist.loop = True

    with patch.object(music_cog, 'cog_failure', new_callable=AsyncMock) as mock_cog_failure:
        await music_cog.skip_song(ctx)

        ctx.message.channel.send.assert_awaited_with(
            "*Loop* is **ON**. Please disable *Loop* before skipping."
        )
        mock_cog_failure.assert_awaited()


@pytest.mark.asyncio
async def test_skip_song_success(music_cog, bot):
    """Test the 'skip_song' command when skip is successful."""
    ctx = mock_ctx(bot)
    music_cog.state_machine.get_state = MagicMock(return_value=State.PLAYING)
    music_cog.playlist.loop = False

    with patch.object(music_cog.player, 'skip', new_callable=AsyncMock) as mock_skip:
        await music_cog.skip_song(ctx)

        mock_skip.assert_awaited_with(ctx.message)


# Tests for the 'stop' command
@pytest.mark.asyncio
async def test_stop_command(music_cog, bot):
    """Test the 'stop' command."""
    ctx = mock_ctx(bot)

    with patch.object(music_cog.state_machine, 'stop', new_callable=AsyncMock) as mock_sm_stop, \
         patch.object(music_cog.downloader, 'stop', new_callable=AsyncMock) as mock_dl_stop, \
         patch.object(music_cog.player, 'stop', new_callable=AsyncMock) as mock_player_stop, \
         patch.object(music_cog, 'clear', new_callable=AsyncMock) as mock_clear, \
         patch.object(music_cog, 'cog_success', new_callable=AsyncMock) as mock_cog_success:

        await music_cog.stop(ctx)

        mock_sm_stop.assert_awaited()
        mock_dl_stop.assert_awaited()
        mock_player_stop.assert_awaited()
        mock_clear.assert_awaited_with(None)
        mock_cog_success.assert_awaited_with(ctx.message)
        ctx.message.delete.assert_awaited()


# Tests for the 'clear' command
@pytest.mark.asyncio
async def test_clear_command(music_cog, bot):
    """Test the 'clear' command."""
    ctx = mock_ctx(bot)

    with patch.object(music_cog.downloader, 'clear', new_callable=AsyncMock) as mock_dl_clear, \
         patch.object(music_cog.playlist, 'clear', new_callable=AsyncMock) as mock_pl_clear, \
         patch.object(music_cog, 'cog_success', new_callable=AsyncMock) as mock_cog_success:

        await music_cog.clear(ctx)

        mock_dl_clear.assert_awaited()
        mock_pl_clear.assert_awaited()
        ctx.send.assert_awaited_with("The playlist has been cleared!")
        mock_cog_success.assert_awaited_with(ctx.message)
        ctx.message.delete.assert_awaited()


# Tests for the 'loop' command
@pytest.mark.asyncio
async def test_loop_command(music_cog, bot):
    """Test the 'loop' command."""
    ctx = mock_ctx(bot)

    with patch.object(music_cog.playlist, 'toggle_loop', return_value=True) as mock_toggle_loop, \
         patch.object(music_cog, 'cog_success', new_callable=AsyncMock) as mock_cog_success:

        await music_cog.loop(ctx)

        mock_toggle_loop.assert_called()
        ctx.send.assert_awaited_with("Loop is now **True**.")
        mock_cog_success.assert_awaited_with(ctx.message)


# Tests for the 'shuffle' command
@pytest.mark.asyncio
async def test_shuffle_command(music_cog, bot):
    """Test the 'shuffle' command."""
    ctx = mock_ctx(bot)

    with patch.object(music_cog.playlist, 'toggle_shuffle', return_value=True) as mock_toggle_shuffle, \
         patch.object(music_cog, 'cog_success', new_callable=AsyncMock) as mock_cog_success:

        await music_cog.shuffle(ctx)

        mock_toggle_shuffle.assert_called()
        ctx.send.assert_awaited_with("Shuffle is now **True**.")
        mock_cog_success.assert_awaited_with(ctx.message)


# Tests for the '_playlist' command
@pytest.mark.asyncio
async def test_playlist_command(music_cog, bot):
    """Test the '_playlist' command."""
    ctx = mock_ctx(bot)
    playlist_embed = discord.Embed(title="Playlist")

    with patch.object(music_cog.playlist, 'get_embed', return_value=playlist_embed):
        await music_cog._playlist(ctx)

        ctx.send.assert_awaited_with(embed=playlist_embed)

        # Ensure previous messages' delete methods are AsyncMock
        if music_cog.playlist.sent_message:
            music_cog.playlist.sent_message.delete = AsyncMock()
            await music_cog.playlist.sent_message.delete()
            music_cog.playlist.sent_message.delete.assert_awaited()

        if music_cog.playlist.user_req_message:
            music_cog.playlist.user_req_message.delete = AsyncMock()
            await music_cog.playlist.user_req_message.delete()
            music_cog.playlist.user_req_message.delete.assert_awaited()

        assert music_cog.playlist.sent_message is not None
        assert music_cog.playlist.user_req_message == ctx.message

        await music_cog.cog_success(ctx.message)


# Additional tests for helper methods and error handling can be added similarly.
