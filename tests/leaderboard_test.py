import pytest
from unittest.mock import AsyncMock, MagicMock

import discord

from cogs.leaderboard import Leaderboard


@pytest.fixture
def bot():
    b = MagicMock()
    b.user.id = 999  # bot's own id, excluded from the leaderboard
    return b


@pytest.fixture
def leaderboard_cog(bot):
    return Leaderboard(bot)


def mock_ctx():
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_leaderboard_no_database(leaderboard_cog, bot):
    ctx = mock_ctx()
    bot.get_cog = MagicMock(return_value=None)
    await leaderboard_cog.leaderboard.callback(leaderboard_cog, ctx)
    ctx.send.assert_awaited_once_with("Data storage is not available right now.")


@pytest.mark.asyncio
async def test_leaderboard_excludes_bot_and_orders_top_five(leaderboard_cog, bot):
    ctx = mock_ctx()
    db = MagicMock()
    db.get_all_user_hours = AsyncMock(
        return_value=[
            (1, 5.0),
            (999, 1000.0),  # the bot itself, must be excluded
            (2, 20.0),
            (3, 15.0),
            (4, 1.0),
            (5, 8.0),
            (6, 2.0),
        ]
    )
    bot.get_cog = MagicMock(return_value=db)

    member = MagicMock()
    member.name = "SomeUser"
    bot.get_user = MagicMock(return_value=member)

    await leaderboard_cog.leaderboard.callback(leaderboard_cog, ctx)

    ctx.send.assert_awaited_once()
    message = ctx.send.call_args.args[0]
    assert "🏆 **Leaderboard** 🏆" in message
    assert "#1 SomeUser** - 20.0 hours" in message
    # Only top 5 entries after excluding the bot.
    assert message.count("SomeUser") == 5
    ctx.message.add_reaction.assert_awaited_once_with("✅")


@pytest.mark.asyncio
async def test_leaderboard_falls_back_to_fetch_user_when_uncached(
    leaderboard_cog, bot
):
    ctx = mock_ctx()
    db = MagicMock()
    db.get_all_user_hours = AsyncMock(return_value=[(42, 3.0)])
    bot.get_cog = MagicMock(return_value=db)

    bot.get_user = MagicMock(return_value=None)
    fetched = MagicMock()
    fetched.name = "FetchedUser"
    bot.fetch_user = AsyncMock(return_value=fetched)

    await leaderboard_cog.leaderboard.callback(leaderboard_cog, ctx)

    bot.fetch_user.assert_awaited_once_with(42)
    message = ctx.send.call_args.args[0]
    assert "FetchedUser" in message


@pytest.mark.asyncio
async def test_leaderboard_shows_id_when_user_unresolvable(leaderboard_cog, bot):
    ctx = mock_ctx()
    db = MagicMock()
    db.get_all_user_hours = AsyncMock(return_value=[(42, 3.0)])
    bot.get_cog = MagicMock(return_value=db)

    bot.get_user = MagicMock(return_value=None)
    bot.fetch_user = AsyncMock(side_effect=discord.DiscordException("user not found"))

    await leaderboard_cog.leaderboard.callback(leaderboard_cog, ctx)

    message = ctx.send.call_args.args[0]
    assert "ID: 42" in message
