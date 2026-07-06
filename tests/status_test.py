import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

import discord
from discord.ext import commands

from cogs.status import Status


def mock_ctx():
    ctx = Mock()
    ctx.send = AsyncMock()
    ctx.message = Mock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    ctx.author = Mock(id=42)
    return ctx


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.fixture
def status_cog(bot):
    return Status(bot)


def _db_returning(hours):
    db = MagicMock()
    db.get_user_hours = AsyncMock(return_value=hours)
    return db


@pytest.mark.asyncio
async def test_status_under_one_hour(status_cog, bot):
    bot.add_cog = None  # not used; get_cog is monkeypatched directly below
    bot.get_cog = Mock(return_value=_db_returning(0.4))
    ctx = mock_ctx()
    await status_cog.status.callback(status_cog, ctx)
    ctx.send.assert_awaited_once_with(
        "You have not spent an hour yet on the server. Disconnect to refresh."
    )
    ctx.message.add_reaction.assert_awaited_once_with("✅")


@pytest.mark.asyncio
async def test_status_rounds_and_reports_hours(status_cog, bot):
    bot.get_cog = Mock(return_value=_db_returning(12.3456))
    ctx = mock_ctx()
    await status_cog.status.callback(status_cog, ctx)
    ctx.send.assert_awaited_once_with(
        "You have spent **12.35** hours in the server since 2024."
    )


@pytest.mark.asyncio
async def test_status_exactly_one_hour_counts_as_spent(status_cog, bot):
    bot.get_cog = Mock(return_value=_db_returning(1.0))
    ctx = mock_ctx()
    await status_cog.status.callback(status_cog, ctx)
    ctx.send.assert_awaited_once_with(
        "You have spent **1.0** hours in the server since 2024."
    )
