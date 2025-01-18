import pytest
from unittest.mock import AsyncMock, Mock
from discord.ext import commands
import discord

from cogs.emoji import Emoji  

# Helper function to create a mock Context
def mock_ctx(message_content):
    """Creates a mock Discord context with the specified message content."""
    ctx = Mock()
    ctx.send = AsyncMock()
    ctx.message = Mock()
    ctx.message.content = message_content
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    return ctx

# Fixture for bot instance
@pytest.fixture
def bot():
    """Creates a mock Discord bot instance."""
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix='!', intents=intents)
    return bot

# Fixture for Emoji cog instance
@pytest.fixture
def emoji_cog(bot):
    """Creates an instance of the Emoji cog."""
    return Emoji(bot)

# Parametrized test for the emoji command
@pytest.mark.asyncio
@pytest.mark.parametrize("message_content, expected_emoji_text", [
    # Test case: Normal input
    ('!emoji Hello World!', ':regional_indicator_h: :regional_indicator_e: '
     ':regional_indicator_l: :regional_indicator_l: :regional_indicator_o:   '
     ':regional_indicator_w: :regional_indicator_o: :regional_indicator_r: '
     ':regional_indicator_l: :regional_indicator_d: ❕ '),
    # Test case: Input with numbers and special characters
    ('!emoji 123?!', '1 2 3 ❔ ❕ '),
    # Test case: Empty input
    ('!emoji', ''),
])
async def test_emoji_command(emoji_cog, message_content, expected_emoji_text):
    """Tests the emoji command with various inputs."""
    ctx = mock_ctx(message_content)
    await emoji_cog.emoji(ctx)
    ctx.send.assert_awaited_once_with(expected_emoji_text)
    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_awaited_once_with("✅")

# Parametrized test for text_to_emoji method
@pytest.mark.asyncio
@pytest.mark.parametrize("input_text, expected_output", [
    # Test case: Letters
    ('abcXYZ', ':regional_indicator_a: :regional_indicator_b: '
     ':regional_indicator_c: :regional_indicator_x: :regional_indicator_y: '
     ':regional_indicator_z: '),
    # Test case: Numbers and special characters
    ('123?!#', '1 2 3 ❔ ❕ # '),
    # Test case: Empty string
    ('', ''),
    # Test case: Mixed input
    ('Hello World!', ':regional_indicator_h: :regional_indicator_e: '
     ':regional_indicator_l: :regional_indicator_l: :regional_indicator_o:   '
     ':regional_indicator_w: :regional_indicator_o: :regional_indicator_r: '
     ':regional_indicator_l: :regional_indicator_d: ❕ '),
])
async def test_text_to_emoji(emoji_cog, input_text, expected_output):
    """Tests the text_to_emoji method with various inputs."""
    emoji_text = await emoji_cog.text_to_emoji(input_text)
    assert emoji_text == expected_output

# Test for exception handling in ctx.send (if applicable)
@pytest.mark.asyncio
async def test_emoji_command_send_exception(emoji_cog):
    """Tests the emoji command when ctx.send raises an exception."""
    message_content = '!emoji Hello'
    ctx = mock_ctx(message_content)
    ctx.send.side_effect = Exception("Send failed")
    with pytest.raises(Exception) as exc_info:
        await emoji_cog.emoji(ctx)
    assert str(exc_info.value) == "Send failed"
    ctx.message.clear_reactions.assert_not_awaited()
    ctx.message.add_reaction.assert_not_awaited()

# Test for exception in ctx.message.clear_reactions
@pytest.mark.asyncio
async def test_emoji_command_clear_reactions_exception(emoji_cog):
    """Tests the emoji command when clear_reactions raises an exception."""
    message_content = '!emoji Hello'
    ctx = mock_ctx(message_content)
    ctx.message.clear_reactions.side_effect = Exception("Clear reactions failed")
    with pytest.raises(Exception) as exc_info:
        await emoji_cog.emoji(ctx)
    assert str(exc_info.value) == "Clear reactions failed"
    ctx.send.assert_awaited_once()
    ctx.message.add_reaction.assert_not_awaited()
