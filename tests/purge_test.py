import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from discord.ext import commands
from discord import Message, TextChannel, ClientUser, Member


def make_command(name, aliases):
    """Build a mock command with a real .name/.aliases (MagicMock(name=...)
    sets the mock's repr, not the .name attribute)."""
    cmd = MagicMock()
    cmd.name = name
    cmd.aliases = aliases
    return cmd


@pytest.fixture
def mock_config():
    return {"prefix": "!"}


@pytest.fixture
def mock_bot(mock_config):
    bot = MagicMock(spec=commands.Bot)
    bot.main_channel = MagicMock(spec=TextChannel)
    bot.user = MagicMock(spec=ClientUser)
    bot.user.id = 123456789
    bot.walk_commands = MagicMock(
        return_value=[
            make_command("ping", []),
            make_command("echo", ["repeat"]),
        ]
    )
    return bot


@pytest.fixture
def purge_cog_instance(mock_bot, mock_config):
    from cogs.purge import Purge

    cog = Purge(mock_bot, mock_config)
    cog.set_cmd_list()  # normally done in cog_load
    return cog


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.message = MagicMock(spec=Message)
    ctx.channel = MagicMock(spec=TextChannel)
    ctx.author = MagicMock(spec=Member)
    ctx.message.add_reaction = AsyncMock()
    ctx.channel.purge = AsyncMock(return_value=[])
    ctx.bot = MagicMock()
    return ctx


def test_set_cmd_list(purge_cog_instance, mock_bot):
    assert "ping" in purge_cog_instance.cmd_list
    assert "echo" in purge_cog_instance.cmd_list
    assert "repeat" in purge_cog_instance.cmd_list

    mock_bot.walk_commands.return_value = [make_command("foo", ["bar", "baz"])]
    purge_cog_instance.set_cmd_list()
    assert "foo" in purge_cog_instance.cmd_list
    assert "bar" in purge_cog_instance.cmd_list
    assert "baz" in purge_cog_instance.cmd_list


def test_is_bot_or_command_no_params(purge_cog_instance):
    message = MagicMock(spec=Message)

    message.author = purge_cog_instance.bot.user
    assert purge_cog_instance.is_bot_or_command(message, params=False)

    message.author = MagicMock(spec=Member)
    message.content = "!ping"
    assert purge_cog_instance.is_bot_or_command(message, params=False)

    message.content = "!notacommand"
    assert not purge_cog_instance.is_bot_or_command(message, params=False)


def test_is_bot_or_command_with_params(purge_cog_instance):
    message = MagicMock(spec=Message)

    message.author = purge_cog_instance.bot.user
    assert purge_cog_instance.is_bot_or_command(message, params=True)

    message.author = MagicMock(spec=Member)
    message.content = "!echo hello"
    assert purge_cog_instance.is_bot_or_command(message, params=True)

    message.content = "!notexists something"
    assert not purge_cog_instance.is_bot_or_command(message, params=True)


@pytest.mark.asyncio
async def test_purge_command_success(purge_cog_instance, mock_ctx):
    await purge_cog_instance.purge.callback(purge_cog_instance, mock_ctx)
    mock_ctx.message.add_reaction.assert_awaited_once_with("⌛")
    assert mock_ctx.channel.purge.await_count == 2
    purge_calls = mock_ctx.channel.purge.await_args_list
    assert purge_calls[0].kwargs["limit"] == 50
    assert purge_calls[1].kwargs["limit"] == 50


@pytest.mark.asyncio
async def test_purge_job(purge_cog_instance, mock_bot):
    mock_bot.main_channel.purge = AsyncMock(return_value=[])
    await purge_cog_instance.purge_job()
    assert mock_bot.main_channel.purge.await_count == 2


@pytest.mark.asyncio
async def test_purge_job_when_no_main_channel(purge_cog_instance, mock_bot):
    type(mock_bot).main_channel = PropertyMock(return_value=None)
    await purge_cog_instance.purge_job()


@pytest.mark.asyncio
async def test_cog_setup(monkeypatch):
    from cogs import purge

    monkeypatch.setattr(purge, "load_config", lambda: {"prefix": "!"})
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    await purge.setup(bot)
    bot.add_cog.assert_awaited_once()
