import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from cogs.status import Status


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    intents.message_content = True
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.fixture
def status_cog(bot):
    return Status(bot)


def mock_ctx():
    ctx = MagicMock()
    ctx.author = MagicMock()
    ctx.author.id = 111
    ctx.send = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_status_no_database(status_cog, bot):
    ctx = mock_ctx()
    bot.get_cog = MagicMock(return_value=None)
    await status_cog.status.callback(status_cog, ctx)
    ctx.send.assert_awaited_once_with("Data storage is not available right now.")


@pytest.mark.asyncio
async def test_status_under_one_hour(status_cog, bot):
    ctx = mock_ctx()
    db = MagicMock()
    db.get_user_hours = AsyncMock(return_value=0.5)
    bot.get_cog = MagicMock(return_value=db)

    await status_cog.status.callback(status_cog, ctx)

    ctx.send.assert_awaited_once_with(
        "You have not spent an hour yet on the server. Disconnect to refresh."
    )
    ctx.message.add_reaction.assert_awaited_once_with("✅")


@pytest.mark.asyncio
async def test_status_reports_rounded_hours(status_cog, bot):
    ctx = mock_ctx()
    db = MagicMock()
    db.get_user_hours = AsyncMock(return_value=12.3456)
    bot.get_cog = MagicMock(return_value=db)

    await status_cog.status.callback(status_cog, ctx)

    db.get_user_hours.assert_awaited_once_with(111)
    ctx.send.assert_awaited_once_with(
        "You have spent **12.35** hours in the server since 2024."
    )
