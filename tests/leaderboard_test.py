from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord.ext import commands

from cogs.leaderboard import Leaderboard


@pytest.fixture
def bot():
    b = AsyncMock(spec=commands.Bot)
    b.user = MagicMock(id=999)
    return b


@pytest.fixture
def cog(bot):
    return Leaderboard(bot)


def mock_ctx():
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock()
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


def make_member(name):
    member = MagicMock()
    member.name = name
    return member


@pytest.mark.asyncio
async def test_leaderboard_excludes_bot_and_sorts_top_five(cog, bot):
    ctx = mock_ctx()
    user_hours_list = [
        (999, 999.0),  # bot user, must be excluded
        (1, 5.111),
        (2, 20.0),
        (3, 15.0),
        (4, 1.0),
        (5, 2.0),
        (6, 30.0),  # 6th distinct user, should be cut by top-5 limit
    ]
    db = MagicMock()
    db.get_all_user_hours = AsyncMock(return_value=user_hours_list)
    bot.get_cog = MagicMock(return_value=db)

    members_by_id = {
        6: make_member("Fastest"),
        2: make_member("Second"),
        3: make_member("Third"),
        5: make_member("Fifth"),
        1: make_member("First"),
    }

    async def fake_resolve(user_id):
        return members_by_id[user_id]

    with patch.object(cog, "_resolve_user", side_effect=fake_resolve):
        await cog.leaderboard.callback(cog, ctx)

    ctx.send.assert_awaited_once()
    (message,), _ = ctx.send.call_args
    assert "999" not in message  # bot's own hours entry must be excluded entirely
    # Only top 5 by hours should appear; user_id 4 (1.0 hours) should be dropped.
    assert "ID: 4" not in message
    assert message.index("Fastest") < message.index("Second")
    assert message.index("Second") < message.index("Third")
    assert message.index("Third") < message.index("Fifth")
    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_awaited_once_with("✅")


@pytest.mark.asyncio
async def test_leaderboard_falls_back_to_id_when_user_unresolvable(cog, bot):
    ctx = mock_ctx()
    db = MagicMock()
    db.get_all_user_hours = AsyncMock(return_value=[(42, 10.0)])
    bot.get_cog = MagicMock(return_value=db)

    with patch.object(cog, "_resolve_user", AsyncMock(side_effect=Exception("nope"))):
        await cog.leaderboard.callback(cog, ctx)

    (message,), _ = ctx.send.call_args
    assert "ID: 42" in message


@pytest.mark.asyncio
async def test_leaderboard_empty_list_sends_header_only(cog, bot):
    ctx = mock_ctx()
    db = MagicMock()
    db.get_all_user_hours = AsyncMock(return_value=[])
    bot.get_cog = MagicMock(return_value=db)

    await cog.leaderboard.callback(cog, ctx)

    (message,), _ = ctx.send.call_args
    assert message.strip() == "🏆 **Leaderboard** 🏆"


@pytest.mark.asyncio
async def test_resolve_user_prefers_cache_over_fetch(cog, bot):
    cached_user = make_member("Cached")
    bot.get_user = MagicMock(return_value=cached_user)
    bot.fetch_user = AsyncMock()

    result = await cog._resolve_user(1)

    assert result is cached_user
    bot.fetch_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_user_fetches_when_not_cached(cog, bot):
    fetched_user = make_member("Fetched")
    bot.get_user = MagicMock(return_value=None)
    bot.fetch_user = AsyncMock(return_value=fetched_user)

    result = await cog._resolve_user(2)

    assert result is fetched_user
    bot.fetch_user.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_setup_adds_cog(bot):
    from cogs.leaderboard import setup

    bot.add_cog = AsyncMock()
    await setup(bot)

    bot.add_cog.assert_awaited_once()
    assert isinstance(bot.add_cog.call_args[0][0], Leaderboard)
