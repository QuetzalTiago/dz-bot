import pytest
from unittest.mock import AsyncMock, MagicMock

from discord.ext import commands
from discord import Message, TextChannel, ClientUser, Member, Guild


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


def make_guild(name, channel_names):
    guild = MagicMock(spec=Guild)
    guild.name = name
    channels = []
    for position, channel_name in enumerate(channel_names):
        channel = MagicMock(spec=TextChannel)
        channel.name = channel_name
        channel.position = position
        channel.purge = AsyncMock(return_value=[])
        channels.append(channel)
    guild.text_channels = channels
    return guild


@pytest.fixture
def mock_bot(mock_config):
    bot = MagicMock(spec=commands.Bot)
    bot.guilds = [make_guild("guild-one", ["general", "random"])]
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
async def test_purge_job_purges_first_channel_of_every_guild(
    purge_cog_instance, mock_bot
):
    second_guild = make_guild("guild-two", ["announcements", "general"])
    mock_bot.guilds.append(second_guild)

    await purge_cog_instance.purge_job()

    first_channel = mock_bot.guilds[0].text_channels[0]
    second_channel = second_guild.text_channels[0]
    assert first_channel.purge.await_count == 2
    assert second_channel.purge.await_count == 2
    # Only the lowest-position channel per guild is touched.
    assert mock_bot.guilds[0].text_channels[1].purge.await_count == 0
    assert second_guild.text_channels[1].purge.await_count == 0


@pytest.mark.asyncio
async def test_purge_job_skips_guild_with_no_text_channels(
    purge_cog_instance, mock_bot
):
    empty_guild = make_guild("empty-guild", [])
    mock_bot.guilds.append(empty_guild)

    await purge_cog_instance.purge_job()  # must not raise

    assert mock_bot.guilds[0].text_channels[0].purge.await_count == 2


@pytest.mark.asyncio
async def test_cog_setup(monkeypatch):
    from cogs import purge

    monkeypatch.setattr(purge, "load_config", lambda: {"prefix": "!"})
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    await purge.setup(bot)
    bot.add_cog.assert_awaited_once()
