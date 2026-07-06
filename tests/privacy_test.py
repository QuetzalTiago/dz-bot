import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from cogs.privacy import Privacy


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    intents.message_content = True
    b = commands.Bot(command_prefix="!", intents=intents)
    b.online_users = {}
    return b


@pytest.fixture
def privacy_cog(bot):
    return Privacy(bot)


def mock_ctx(bot, author_id=123):
    ctx = MagicMock()
    ctx.bot = bot
    ctx.author = MagicMock()
    ctx.author.id = author_id
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_my_data_no_database(privacy_cog, bot):
    ctx = mock_ctx(bot)
    await privacy_cog.my_data.callback(privacy_cog, ctx)
    ctx.send.assert_awaited_once_with("Data storage is not available right now.")


@pytest.mark.asyncio
async def test_my_data_reports_stored_data(privacy_cog, bot):
    ctx = mock_ctx(bot)
    db = MagicMock()
    db.get_user_data = AsyncMock(
        return_value={"tracked_seconds": 7200, "songs_requested": 5}
    )
    bot.get_cog = MagicMock(return_value=db)

    await privacy_cog.my_data.callback(privacy_cog, ctx)

    db.get_user_data.assert_awaited_once_with(123)
    ctx.send.assert_awaited_once()
    embed = ctx.send.call_args.kwargs["embed"]
    assert embed.fields[0].value == "2.0 hours"
    assert embed.fields[1].value == "5"


@pytest.mark.asyncio
async def test_forget_me_no_database(privacy_cog, bot):
    ctx = mock_ctx(bot)
    await privacy_cog.forget_me.callback(privacy_cog, ctx)
    ctx.send.assert_awaited_once_with("Data storage is not available right now.")


@pytest.mark.asyncio
async def test_forget_me_erases_data_and_online_state(privacy_cog, bot):
    ctx = mock_ctx(bot, author_id=456)
    bot.online_users[456] = "some-join-time"
    db = MagicMock()
    db.delete_user_data = AsyncMock()
    bot.get_cog = MagicMock(return_value=db)

    await privacy_cog.forget_me.callback(privacy_cog, ctx)

    db.delete_user_data.assert_awaited_once_with(456)
    assert 456 not in bot.online_users
    ctx.send.assert_awaited_once_with("Your stored data has been erased.")


@pytest.mark.asyncio
async def test_forget_me_when_not_online(privacy_cog, bot):
    ctx = mock_ctx(bot, author_id=789)
    db = MagicMock()
    db.delete_user_data = AsyncMock()
    bot.get_cog = MagicMock(return_value=db)

    # Should not raise even though the user isn't in online_users.
    await privacy_cog.forget_me.callback(privacy_cog, ctx)

    ctx.send.assert_awaited_once_with("Your stored data has been erased.")
