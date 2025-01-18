# test_div_cog.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from discord.ext import commands
from discord import Intents
from cogs.div import Div  
import requests  # Import requests for exceptions

# Fixtures for bot and cog
@pytest.fixture
def bot():
    intents = Intents.default()
    intents.message_content = True  # Enable message content intent
    return commands.Bot(command_prefix='!', intents=intents)

@pytest.fixture
def div_cog(bot):
    return Div(bot)

# Helper function to create a mock context
def mock_ctx(message_content):
    ctx = MagicMock()
    ctx.message.content = message_content
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    ctx.message.guild = MagicMock()
    ctx.message.author = MagicMock()
    return ctx

# Test for successful execution
@pytest.mark.asyncio
async def test_div_command_success(div_cog):
    ctx = mock_ctx('div Standard')

    with patch('cogs.div.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            'lines': [
                {'currencyTypeName': 'Divine Orb', 'chaosEquivalent': '200'}
            ]
        }
        mock_get.return_value = mock_response

        await div_cog.div.callback(div_cog, ctx)

    ctx.message.add_reaction.assert_any_call('⌛')
    ctx.message.add_reaction.assert_any_call('✅')
    ctx.send.assert_called_with('Current Divine price in Standard league: **200 Chaos**')

# Test when no league is specified
@pytest.mark.asyncio
async def test_div_command_no_league(div_cog):
    ctx = mock_ctx('div')

    await div_cog.div.callback(div_cog, ctx)

    ctx.message.clear_reactions.assert_called_once()
    ctx.message.add_reaction.assert_any_call('❌')
    ctx.send.assert_called_with("Specify the league, for example: 'div necropolis'")

# Test when Divine Orb is not found in the API response
@pytest.mark.asyncio
async def test_div_command_divine_orb_not_found(div_cog):
    ctx = mock_ctx('div Standard')

    with patch('cogs.div.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {'lines': []}
        mock_get.return_value = mock_response

        await div_cog.div.callback(div_cog, ctx)

    ctx.message.clear_reactions.assert_called_once()
    ctx.message.add_reaction.assert_any_call('❌')
    ctx.send.assert_called_with(
        'Error fetching data for the specified league. Please check the league name and try again.'
    )

# Test when an HTTP error occurs
@pytest.mark.asyncio
async def test_div_command_http_error(div_cog):
    ctx = mock_ctx('div NonexistentLeague')

    with patch('cogs.div.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('404 Client Error')
        mock_get.return_value = mock_response

        await div_cog.div.callback(div_cog, ctx)

    ctx.message.clear_reactions.assert_called_once()
    ctx.message.add_reaction.assert_any_call('❌')
    ctx.send.assert_called_with(
        'Error fetching data for the specified league. Please check the league name and try again.'
    )

# Test when a general exception occurs
@pytest.mark.asyncio
async def test_div_command_exception(div_cog):
    ctx = mock_ctx('div Standard')

    with patch('cogs.div.requests.get') as mock_get:
        mock_get.side_effect = Exception('Some error')

        await div_cog.div.callback(div_cog, ctx)

    ctx.message.clear_reactions.assert_called_once()
    ctx.message.add_reaction.assert_any_call('❌')
    ctx.send.assert_called_with(
        'Error fetching data for the specified league. Please check the league name and try again.'
    )
