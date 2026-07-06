import pytest
from unittest.mock import AsyncMock, MagicMock

from discord.ext import commands
from discord import ClientUser

from cogs.leaderboard import Leaderboard


@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=commands.Bot)
    bot.user = MagicMock(spec=ClientUser)
    bot.user.id = 999
    return bot


@pytest.fixture
def leaderboard_cog(mock_bot):
    return Leaderboard(mock_bot)


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    return ctx


def make_db(hours_list):
    db = MagicMock()
    db.get_all_user_hours = AsyncMock(return_value=hours_list)
    return db


@pytest.mark.asyncio
async def test_leaderboard_excludes_bot_and_sorts_top_five(
    leaderboard_cog, mock_bot, mock_ctx
):
    hours = [(1, 5.0), (2, 20.0), (999, 999.0), (3, 1.0), (4, 15.0), (5, 3.0), (6, 8.0)]
    mock_bot.get_cog.return_value = make_db(hours)

    members = {}
    for uid in (2, 4, 6, 1, 5):
        member = MagicMock()
        member.name = f"user{uid}"
        members[uid] = member
    mock_bot.get_user.side_effect = lambda uid: members.get(uid)

    await leaderboard_cog.leaderboard.callback(leaderboard_cog, mock_ctx)

    mock_bot.get_cog.assert_called_with("Database")
    sent_message = mock_ctx.send.await_args.args[0]

    assert "#1 user2" in sent_message
    assert "20.0 hours" in sent_message
    assert "999" not in sent_message
    # Only the top 5 (by hours, bot excluded) should be listed.
    assert sent_message.count("**#") == 5
    mock_ctx.message.add_reaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_leaderboard_falls_back_to_id_when_user_unresolvable(
    leaderboard_cog, mock_bot, mock_ctx
):
    hours = [(42, 10.0)]
    mock_bot.get_cog.return_value = make_db(hours)
    mock_bot.get_user.return_value = None
    mock_bot.fetch_user = AsyncMock(side_effect=Exception("not found"))

    await leaderboard_cog.leaderboard.callback(leaderboard_cog, mock_ctx)

    sent_message = mock_ctx.send.await_args.args[0]
    assert "ID: 42" in sent_message


@pytest.mark.asyncio
async def test_resolve_user_fetches_when_not_cached(leaderboard_cog, mock_bot):
    mock_bot.get_user.return_value = None
    fetched = MagicMock()
    mock_bot.fetch_user = AsyncMock(return_value=fetched)

    result = await leaderboard_cog._resolve_user(7)

    mock_bot.fetch_user.assert_awaited_once_with(7)
    assert result is fetched


@pytest.mark.asyncio
async def test_resolve_user_uses_cache_when_available(leaderboard_cog, mock_bot):
    cached = MagicMock()
    mock_bot.get_user.return_value = cached
    mock_bot.fetch_user = AsyncMock()

    result = await leaderboard_cog._resolve_user(7)

    mock_bot.fetch_user.assert_not_awaited()
    assert result is cached


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    from cogs import leaderboard

    await leaderboard.setup(bot)
    bot.add_cog.assert_awaited_once()
