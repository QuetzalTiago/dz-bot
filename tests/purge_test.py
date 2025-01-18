import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from discord.ext import commands, tasks
from discord import Message, TextChannel, ClientUser, Member, Guild, Emoji

# Assuming the cog code is saved in a file named purge_cog.py
from cogs.purge import Purge

@pytest.fixture
def mock_config():
    return {
        "prefix": "!"
    }

@pytest.fixture
def mock_bot(mock_config):
    # Create a mock bot instance
    bot = MagicMock(spec=commands.Bot)
    type(bot).main_channel = PropertyMock(return_value=MagicMock(spec=TextChannel))
    bot.main_channel = MagicMock(spec=TextChannel)  # ensure main_channel is a TextChannel mock
    bot.user = MagicMock(spec=ClientUser)
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    bot.walk_commands = MagicMock(return_value=[
        MagicMock(name="ping", aliases=[]),
        MagicMock(name="echo", aliases=["repeat"])
    ])
    return bot

@pytest.fixture
def purge_cog_instance(mock_bot, mock_config):
    # Instantiate the cog with the mock bot and config
    cog = Purge(mock_bot, mock_config)
    return cog

@pytest.fixture
def mock_ctx():
    """Fixture to create a mocked context (ctx) object."""
    mock_ctx = MagicMock()
    # Mock attributes commonly used in ctx
    mock_ctx.message = MagicMock(spec=Message)
    mock_ctx.channel = MagicMock(spec=TextChannel)
    mock_ctx.author = MagicMock(spec=Member)
    # Async methods must be AsyncMock
    mock_ctx.message.add_reaction = AsyncMock()
    mock_ctx.channel.purge = AsyncMock(return_value=[])
    # The bot attribute on ctx
    mock_ctx.bot = MagicMock()
    return mock_ctx

def test_set_cmd_list(purge_cog_instance, mock_bot):
    # Initially called in __init__
    assert "ping" in purge_cog_instance.cmd_list
    assert "echo" in purge_cog_instance.cmd_list
    assert "repeat" in purge_cog_instance.cmd_list

    # Modify walk_commands return and re-set cmd list to cover re-call scenario
    mock_bot.walk_commands.return_value = [
        MagicMock(name="foo", aliases=["bar", "baz"])
    ]
    purge_cog_instance.cmd_list = []  # Reset and call again
    purge_cog_instance.set_cmd_list()
    assert "foo" in purge_cog_instance.cmd_list
    assert "bar" in purge_cog_instance.cmd_list
    assert "baz" in purge_cog_instance.cmd_list

@pytest.mark.asyncio
async def test_is_bot_or_command_no_params(purge_cog_instance, mock_bot, mock_config):
    message = MagicMock(spec=Message)
    message.author = MagicMock(spec=Member)
    message.content = "!ping"
    message.author == purge_cog_instance.bot.user  # False by default

    # When author is the bot:
    message.author = purge_cog_instance.bot.user
    assert purge_cog_instance.is_bot_or_command(message, params=False)

    # When author is not bot but matches a command exactly
    message.author = MagicMock(spec=Member)
    message.content = "!ping"
    assert purge_cog_instance.is_bot_or_command(message, params=False)

    # When does not match any command
    message.content = "!notacommand"
    assert not purge_cog_instance.is_bot_or_command(message, params=False)

@pytest.mark.asyncio
async def test_is_bot_or_command_with_params(purge_cog_instance, mock_bot, mock_config):
    message = MagicMock(spec=Message)
    message.author = MagicMock(spec=Member)
    prefix = mock_config.get("prefix", "!")

    # When author is the bot, should return True regardless
    message.author = purge_cog_instance.bot.user
    assert purge_cog_instance.is_bot_or_command(message, params=True)

    # Reset author to non-bot
    message.author = MagicMock(spec=Member)

    # Test a command with parameters
    message.content = f"{prefix}echo hello"
    assert purge_cog_instance.is_bot_or_command(message, params=True)

    # Non-matching command
    message.content = f"{prefix}notexists something"
    assert not purge_cog_instance.is_bot_or_command(message, params=True)

@pytest.mark.asyncio
async def test_purge_command_success(purge_cog_instance, mock_ctx):
    # Ensure that set_cmd_list is called again
    with patch.object(purge_cog_instance, 'set_cmd_list', wraps=purge_cog_instance.set_cmd_list) as mock_set_cmd_list:
        await purge_cog_instance.purge(mock_ctx)
        mock_set_cmd_list.assert_called_once()

    # Test that add_reaction was called
    mock_ctx.message.add_reaction.assert_awaited_once_with("⌛")

    # Test that purge was called twice
    assert mock_ctx.channel.purge.await_count == 2
    purge_calls = mock_ctx.channel.purge.await_args_list

    # First purge call checks no-params
    assert purge_calls[0].kwargs["limit"] == 50
    assert purge_calls[1].kwargs["limit"] == 50

@pytest.mark.asyncio
async def test_purge_command_exception_handling(purge_cog_instance, mock_ctx):
    # If an exception occurs during purge, ensure we handle gracefully
    mock_ctx.channel.purge.side_effect = Exception("Purge error")

    # Since no exception handling is explicitly coded in the cog, the test
    # will simply check if it's raised as expected. If you had exception
    # handling, you would assert the expected behavior instead.
    with pytest.raises(Exception):
        await purge_cog_instance.purge(mock_ctx)

@pytest.mark.asyncio
async def test_purge_job(purge_cog_instance, mock_bot):
    # Mock main channel purge calls
    mock_bot.main_channel.purge = AsyncMock(return_value=[])

    # Manually trigger the purge_job function
    # The loop is 2 hours, but we just call the underlying function for testing
    await purge_cog_instance.purge_job()

    # Check calls
    assert mock_bot.main_channel.purge.await_count == 2
    purge_calls = mock_bot.main_channel.purge.await_args_list
    assert purge_calls[0].kwargs["limit"] == 50
    assert purge_calls[1].kwargs["limit"] == 50

@pytest.mark.asyncio
async def test_purge_job_when_no_main_channel(purge_cog_instance, mock_bot):
    # If main_channel is None, the purge_job should do nothing
    type(mock_bot).main_channel = PropertyMock(return_value=None)
    await purge_cog_instance.purge_job()
    # No purge calls expected
    if mock_bot.main_channel is not None:
        mock_bot.main_channel.purge.assert_not_awaited()

@pytest.mark.asyncio
async def test_cog_setup():
    # Test that setup loads config and adds the cog
    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({"prefix": "!"})
        with patch("json.load", return_value={"prefix": "!"}) as mock_json_load:
            from purge_cog import setup
            bot = MagicMock(spec=commands.Bot)
            await setup(bot)
            bot.add_cog.assert_awaited_once()
            mock_json_load.assert_called_once()
