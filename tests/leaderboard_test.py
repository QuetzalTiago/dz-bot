import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

import discord
from discord.ext import commands

from cogs.leaderboard import Leaderboard


def mock_ctx():
    ctx = Mock()
    ctx.send = AsyncMock()
    ctx.message = Mock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    return ctx


@pytest.fixture
def bot():
    b = MagicMock(spec=commands.Bot)
    b.user = Mock(id=999)
    return b


@pytest.fixture
def leaderboard_cog(bot):
    return Leaderboard(bot)


def _named_user(name):
    user = Mock()
    user.name = name
    return user


@pytest.mark.asyncio
async def test_leaderboard_orders_by_hours_desc_and_excludes_bot(
    leaderboard_cog, bot
):
    # Bot's own id (999) must never show up even if the DB has an entry for it.
    hours = [
        (999, 999.0),
        (1, 5.0),
        (2, 20.0),
        (3, 1.0),
        (4, 10.0),
        (5, 7.0),
        (6, 2.0),
    ]
    db = MagicMock()
    db.get_all_user_hours = AsyncMock(return_value=hours)
    bot.get_cog = Mock(return_value=db)
    bot.get_user = Mock(side_effect=lambda uid: _named_user(f"user{uid}"))

    ctx = mock_ctx()
    await leaderboard_cog.leaderboard.callback(leaderboard_cog, ctx)

    ctx.send.assert_awaited_once()
    (message,) = ctx.send.call_args.args
    # Top 5 by hours, descending, bot's own entry (999) excluded.
    assert message.index("#1 user2") < message.index("#2 user4")
    assert message.index("#2 user4") < message.index("#3 user5")
    assert message.index("#3 user5") < message.index("#4 user1")
    assert message.index("#4 user1") < message.index("#5 user6")
    assert "user999" not in message
    assert "999.0" not in message
    # Only 5 entries rendered even though 6 non-bot users have hours.
    assert message.count("hours") == 5
    ctx.message.add_reaction.assert_awaited_once_with("✅")


@pytest.mark.asyncio
async def test_leaderboard_falls_back_to_fetch_user_and_id_placeholder(
    leaderboard_cog, bot
):
    db = MagicMock()
    db.get_all_user_hours = AsyncMock(return_value=[(1, 3.0), (2, 1.0)])
    bot.get_cog = Mock(return_value=db)
    # get_user misses (returns None) for the uncached user, fetch_user resolves it.
    bot.get_user = Mock(return_value=None)
    bot.fetch_user = AsyncMock(side_effect=discord.DiscordException("missing"))

    ctx = mock_ctx()
    await leaderboard_cog.leaderboard.callback(leaderboard_cog, ctx)

    (message,) = ctx.send.call_args.args
    # Both users failed to resolve -> rendered by raw ID.
    assert "ID: 1" in message
    assert "ID: 2" in message
