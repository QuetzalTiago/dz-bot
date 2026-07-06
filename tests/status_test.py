import pytest
from unittest.mock import AsyncMock, MagicMock

from discord.ext import commands

from cogs.status import Status


@pytest.fixture
def mock_bot():
    return MagicMock(spec=commands.Bot)


@pytest.fixture
def status_cog(mock_bot):
    return Status(mock_bot)


def mock_ctx():
    ctx = MagicMock()
    ctx.author = MagicMock()
    ctx.author.id = 111
    ctx.send = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    return ctx


def make_db(hours):
    db = MagicMock()
    db.get_user_hours = AsyncMock(return_value=hours)
    return db


@pytest.mark.asyncio
async def test_status_under_an_hour(status_cog, mock_bot):
    ctx = mock_ctx()
    mock_bot.get_cog.return_value = make_db(0.5)

    await status_cog.status.callback(status_cog, ctx)

    mock_bot.get_cog.assert_called_with("Database")
    ctx.send.assert_awaited_once_with(
        "You have not spent an hour yet on the server. Disconnect to refresh."
    )
    ctx.message.add_reaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_status_reports_rounded_hours(status_cog, mock_bot):
    ctx = mock_ctx()
    mock_bot.get_cog.return_value = make_db(12.3456)

    await status_cog.status.callback(status_cog, ctx)

    ctx.send.assert_awaited_once_with(
        "You have spent **12.35** hours in the server since 2024."
    )


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    from cogs import status

    await status.setup(bot)
    bot.add_cog.assert_awaited_once()
