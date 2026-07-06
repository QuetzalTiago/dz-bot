import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

import discord
from discord.ext import commands

from cogs.privacy import Privacy


def mock_ctx():
    ctx = Mock()
    ctx.send = AsyncMock()
    ctx.author = Mock(id=123)
    return ctx


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    b = commands.Bot(command_prefix="!", intents=intents)
    b.online_users = {}
    return b


@pytest.fixture
def privacy_cog(bot):
    return Privacy(bot)


@pytest.mark.asyncio
async def test_my_data_reports_hours_and_song_count(privacy_cog, bot):
    db = MagicMock()
    db.get_user_data = AsyncMock(
        return_value={"tracked_seconds": 7230, "songs_requested": 4}
    )
    bot.get_cog = Mock(return_value=db)

    ctx = mock_ctx()
    await privacy_cog.my_data.callback(privacy_cog, ctx)

    db.get_user_data.assert_awaited_once_with(123)
    ctx.send.assert_awaited_once()
    (kwargs) = ctx.send.call_args.kwargs
    embed = kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    assert embed.fields[0].value == "2.01 hours"
    assert embed.fields[1].value == "4"


@pytest.mark.asyncio
async def test_my_data_no_database(privacy_cog, bot):
    bot.get_cog = Mock(return_value=None)
    ctx = mock_ctx()
    await privacy_cog.my_data.callback(privacy_cog, ctx)
    ctx.send.assert_awaited_once_with("Data storage is not available right now.")


@pytest.mark.asyncio
async def test_forget_me_erases_db_and_in_memory_tracking(privacy_cog, bot):
    db = MagicMock()
    db.delete_user_data = AsyncMock()
    bot.get_cog = Mock(return_value=db)
    bot.online_users = {123: "join-time", 456: "other-join-time"}

    ctx = mock_ctx()
    await privacy_cog.forget_me.callback(privacy_cog, ctx)

    db.delete_user_data.assert_awaited_once_with(123)
    # Only the requesting user's in-memory tracking is dropped.
    assert 123 not in bot.online_users
    assert 456 in bot.online_users
    ctx.send.assert_awaited_once_with("Your stored data has been erased.")


@pytest.mark.asyncio
async def test_forget_me_no_database(privacy_cog, bot):
    bot.get_cog = Mock(return_value=None)
    ctx = mock_ctx()
    await privacy_cog.forget_me.callback(privacy_cog, ctx)
    ctx.send.assert_awaited_once_with("Data storage is not available right now.")
