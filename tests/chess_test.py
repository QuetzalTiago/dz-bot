# test_chess_cog.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from discord.ext import commands, tasks
from discord.ext.commands import Context
from discord import Intents, Embed
from cogs.chess import Chess  
import requests

# Fixtures for bot and cog
@pytest.fixture
def bot():
    intents = Intents.default()
    intents.message_content = True
    return commands.Bot(command_prefix='!', intents=intents)

@pytest.fixture
def chess_cog(bot):
    cog = Chess(bot)
    # Mock the logger to avoid unnecessary logging during tests
    cog.logger = MagicMock()
    # Manually set the lichess_token and headers
    cog.lichess_token = 'test_token'
    cog.headers = {
        "Authorization": "Bearer test_token",
        "Accept": "application/json",
    }
    return cog

# Helper function to create a mock context
def mock_ctx(message_content):
    ctx = MagicMock(spec=Context)
    ctx.message = MagicMock()
    ctx.message.content = message_content
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    ctx.message.guild = MagicMock()
    ctx.message.author = MagicMock()
    return ctx


# Test the cog_load method
@pytest.mark.asyncio
async def test_cog_load(chess_cog):
    # Mock json.load to return a specific config
    config_data = {
        "secrets": {
            "lichessToken": "test_token"
        }
    }
    with patch('builtins.open', new_callable=MagicMock):
        with patch('json.load', return_value=config_data):
            # Mock save_match.cancel() to avoid exception
            chess_cog.save_match.cancel = MagicMock()

            await chess_cog.cog_load()

            # Assert that lichess_token and headers are set
            assert chess_cog.lichess_token == "test_token"
            assert chess_cog.headers == {
                "Authorization": "Bearer test_token",
                "Accept": "application/json",
            }

            # Assert that logger.info was called
            chess_cog.logger.info.assert_called_with("Chess cog loaded and configured.")

# Test the chess command with valid input
@pytest.mark.asyncio
async def test_chess_command_success(chess_cog):
    ctx = mock_ctx('chess 10 5')  # Time control 10 minutes, increment 5 seconds

    # Mock fetch_match_url to return a match URL
    with patch.object(chess_cog, 'fetch_match_url', return_value='https://lichess.org/abcd1234'):
        # Mock save_match.start to avoid starting the actual task
        chess_cog.save_match.start = MagicMock()
        # Mock get_match_id to return a match ID
        with patch.object(chess_cog, 'get_match_id', return_value='abcd1234'):
            await chess_cog.chess.callback(chess_cog, ctx)

            # Assertions
            ctx.message.add_reaction.assert_any_call('⌛')
            ctx.message.clear_reactions.assert_called_once()
            ctx.message.add_reaction.assert_any_call('✅')
            ctx.send.assert_called_with('https://lichess.org/abcd1234')
            chess_cog.save_match.start.assert_called_with(ctx, 'abcd1234')
            chess_cog.logger.info.assert_called_with('Chess match created: https://lichess.org/abcd1234')

# Test invalid time control (non-integer)
@pytest.mark.asyncio
async def test_chess_command_invalid_time_control_non_integer(chess_cog):
    ctx = mock_ctx('chess notanumber')

    await chess_cog.chess.callback(chess_cog, ctx)

    ctx.send.assert_called_with('Time control must be an integer.')

# Test invalid time control (out of range)
@pytest.mark.asyncio
async def test_chess_command_invalid_time_control_out_of_range(chess_cog):
    ctx = mock_ctx('chess 0')  # Less than 1
    await chess_cog.chess.callback(chess_cog, ctx)
    ctx.send.assert_called_with(
        "Invalid time control. Please specify a number of minutes between 1 and 60."
    )

    ctx = mock_ctx('chess 61')  # Greater than 60
    await chess_cog.chess.callback(chess_cog, ctx)
    ctx.send.assert_called_with(
        "Invalid time control. Please specify a number of minutes between 1 and 60."
    )

# Test invalid increment (non-integer)
@pytest.mark.asyncio
async def test_chess_command_invalid_increment_non_integer(chess_cog):
    ctx = mock_ctx('chess 10 notanumber')
    await chess_cog.chess.callback(chess_cog, ctx)
    ctx.send.assert_called_with('Increment must be an integer.')

# Test invalid increment (out of range)
@pytest.mark.asyncio
async def test_chess_command_invalid_increment_out_of_range(chess_cog):
    ctx = mock_ctx('chess 10 -1')  # Less than 0
    await chess_cog.chess.callback(chess_cog, ctx)
    ctx.send.assert_called_with(
        "Invalid increment. Please specify a number of seconds between 0 and 60."
    )

    ctx = mock_ctx('chess 10 61')  # Greater than 60
    await chess_cog.chess.callback(chess_cog, ctx)
    ctx.send.assert_called_with(
        "Invalid increment. Please specify a number of seconds between 0 and 60."
    )

# Test when match creation fails
@pytest.mark.asyncio
async def test_chess_command_match_creation_failed(chess_cog):
    ctx = mock_ctx('chess 10 5')

    with patch.object(chess_cog, 'fetch_match_url', return_value=None):
        # Mock save_match.start to avoid starting the actual task
        chess_cog.save_match.start = MagicMock()

        await chess_cog.chess.callback(chess_cog, ctx)

        # Assertions
        ctx.message.add_reaction.assert_called_with('⌛')
        chess_cog.logger.error.assert_called_with('Failed to create chess match.')

# Test fetch_match_url success
@pytest.mark.asyncio
async def test_fetch_match_url_success(chess_cog):
    ctx = mock_ctx('chess 10 5')

    # Mock requests.post
    with patch('cogs.chess.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'url': 'https://lichess.org/abcd1234'}
        mock_post.return_value = mock_response

        result = await chess_cog.fetch_match_url(ctx, {})

        assert result == 'https://lichess.org/abcd1234'

# Test fetch_match_url failure
@pytest.mark.asyncio
async def test_fetch_match_url_failure(chess_cog):
    ctx = mock_ctx('chess 10 5')

    # Mock requests.post
    with patch('cogs.chess.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'
        mock_post.return_value = mock_response

        result = await chess_cog.fetch_match_url(ctx, {})

        assert result is None
        ctx.send.assert_called_with('There was a problem creating the challenge.')
        chess_cog.logger.error.assert_called_with(
            f'Error creating challenge: {mock_response.status_code} - {mock_response.text}'
        )

# Test fetch_match_url exception
@pytest.mark.asyncio
async def test_fetch_match_url_exception(chess_cog):
    ctx = mock_ctx('chess 10 5')

    # Mock requests.post to raise an exception
    with patch('cogs.chess.requests.post', side_effect=requests.RequestException('Error')):
        result = await chess_cog.fetch_match_url(ctx, {})

        assert result is None
        ctx.send.assert_called_with('An error occurred while connecting to Lichess.')
        chess_cog.logger.exception.assert_called()

# Test get_match_id
def test_get_match_id(chess_cog):
    url = 'https://lichess.org/abcd1234'
    match_id = chess_cog.get_match_id(url)
    assert match_id == 'abcd1234'

# Test create_game_summary_embed with white winning
def test_create_game_summary_embed_white_wins(chess_cog):
    game_id = 'abcd1234'
    game_status = 'mate'
    white_username = 'WhitePlayer'
    black_username = 'BlackPlayer'
    winner = 'white'

    embed = chess_cog.create_game_summary_embed(game_id, game_status, white_username, black_username, winner)
    assert isinstance(embed, Embed)
    assert embed.title == f'{white_username} wins!'
    assert 'White: **WhitePlayer**' in embed.description
    assert 'Black: **BlackPlayer**' in embed.description
    assert f'https://lichess.org/{game_id}' in embed.description

# Test create_game_summary_embed with anonymous players
def test_create_game_summary_embed_anonymous_players(chess_cog):
    game_id = 'abcd1234'
    game_status = 'draw'
    white_username = 'Anonymous'
    black_username = 'Anonymous'
    winner = None

    embed = chess_cog.create_game_summary_embed(game_id, game_status, white_username, black_username, winner)
    assert isinstance(embed, Embed)
    assert embed.title == f'Game ended with **{game_status}**'
    assert embed.description == f'https://lichess.org/{game_id}\n'

# Test save_match when the game has ended
@pytest.mark.asyncio
async def test_save_match_game_ended(chess_cog):
    ctx = mock_ctx('chess 10 5')
    match_id = 'abcd1234'

    # Mock requests.get
    with patch('cogs.chess.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'mate',
            'players': {
                'white': {'user': {'name': 'WhitePlayer'}},
                'black': {'user': {'name': 'BlackPlayer'}}
            },
            'winner': 'white'
        }
        mock_get.return_value = mock_response

        # Mock create_game_summary_embed
        with patch.object(chess_cog, 'create_game_summary_embed') as mock_create_embed:
            mock_embed = MagicMock(spec=Embed)
            mock_create_embed.return_value = mock_embed

            # Mock bot.get_cog('Database').save_chess_game
            database_cog_mock = MagicMock()
            database_cog_mock.save_chess_game = MagicMock()
            chess_cog.bot.get_cog = MagicMock(return_value=database_cog_mock)

            # Mock save_match.cancel
            chess_cog.save_match.cancel = MagicMock()

            await chess_cog.save_match(ctx, match_id)

            ctx.send.assert_called_with(embed=mock_embed)
            database_cog_mock.save_chess_game.assert_called()
            chess_cog.logger.info.assert_called_with(f'Chess game saved: {match_id}')
            chess_cog.save_match.cancel.assert_called()

# Test save_match when there is a request error
@pytest.mark.asyncio
async def test_save_match_request_error(chess_cog):
    ctx = mock_ctx('chess 10 5')
    match_id = 'abcd1234'

    # Mock requests.get
    with patch('cogs.chess.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'
        mock_get.return_value = mock_response

        await chess_cog.save_match(ctx, match_id)

        chess_cog.logger.error.assert_called_with(
            f'Failed to fetch game data for {match_id}: {mock_response.status_code} - {mock_response.text}'
        )
