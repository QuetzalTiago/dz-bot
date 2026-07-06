import pytest
from unittest.mock import AsyncMock, MagicMock

from discord.ext import commands

from cogs.privacy import Privacy


@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=commands.Bot)
    bot.online_users = {}
    return bot


@pytest.fixture
def privacy_cog(mock_bot):
    return Privacy(mock_bot)


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.author.id = 123
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_my_data_reports_tracked_hours_and_songs(privacy_cog, mock_bot, mock_ctx):
    db = MagicMock()
    db.get_user_data = AsyncMock(
        return_value={"tracked_seconds": 7200, "songs_requested": 4}
    )
    mock_bot.get_cog.return_value = db

    await privacy_cog.my_data.callback(privacy_cog, mock_ctx)

    db.get_user_data.assert_awaited_once_with(123)
    mock_ctx.send.assert_awaited_once()
    embed = mock_ctx.send.await_args.kwargs["embed"]
    assert embed.fields[0].value == "2.0 hours"
    assert embed.fields[1].value == "4"


@pytest.mark.asyncio
async def test_my_data_when_database_unavailable(privacy_cog, mock_bot, mock_ctx):
    mock_bot.get_cog.return_value = None

    await privacy_cog.my_data.callback(privacy_cog, mock_ctx)

    mock_ctx.send.assert_awaited_once_with("Data storage is not available right now.")


@pytest.mark.asyncio
async def test_forget_me_erases_data_and_in_memory_tracking(
    privacy_cog, mock_bot, mock_ctx
):
    db = MagicMock()
    db.delete_user_data = AsyncMock()
    mock_bot.get_cog.return_value = db
    mock_bot.online_users = {123: "some-join-time", 456: "other"}

    await privacy_cog.forget_me.callback(privacy_cog, mock_ctx)

    db.delete_user_data.assert_awaited_once_with(123)
    assert 123 not in mock_bot.online_users
    assert 456 in mock_bot.online_users
    mock_ctx.send.assert_awaited_once_with("Your stored data has been erased.")


@pytest.mark.asyncio
async def test_forget_me_when_database_unavailable(privacy_cog, mock_bot, mock_ctx):
    mock_bot.get_cog.return_value = None

    await privacy_cog.forget_me.callback(privacy_cog, mock_ctx)

    mock_ctx.send.assert_awaited_once_with("Data storage is not available right now.")


@pytest.mark.asyncio
async def test_forget_me_when_user_not_in_online_users(privacy_cog, mock_bot, mock_ctx):
    db = MagicMock()
    db.delete_user_data = AsyncMock()
    mock_bot.get_cog.return_value = db
    mock_bot.online_users = {}

    await privacy_cog.forget_me.callback(privacy_cog, mock_ctx)

    mock_ctx.send.assert_awaited_once_with("Your stored data has been erased.")


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    from cogs import privacy

    await privacy.setup(bot)
    bot.add_cog.assert_awaited_once()
