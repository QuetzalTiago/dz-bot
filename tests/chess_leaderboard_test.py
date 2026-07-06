from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import discord
from discord.ext import commands

from cogs.chess_leaderboard import ChessLeaderboard


def mock_ctx():
    ctx = Mock()
    ctx.send = AsyncMock()
    ctx.message = Mock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    return ctx


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.fixture
def leaderboard_cog(bot):
    return ChessLeaderboard(bot)


def make_game(winner, white="alice", black="bob"):
    return SimpleNamespace(
        winner=winner,
        players={
            "white": {"user": {"name": white}},
            "black": {"user": {"name": black}},
        },
    )


def test_calculate_leaderboard_counts_wins_and_win_rate(leaderboard_cog):
    games = [
        make_game("white", "alice", "bob"),
        make_game("white", "alice", "carol"),
        make_game("black", "alice", "bob"),
    ]
    leaderboard = leaderboard_cog.calculate_leaderboard(games)

    stats = {name: (wins, rate) for name, wins, rate in leaderboard}
    # alice: 3 games, 2 wins -> 66.67%
    assert stats["alice"] == (2, pytest.approx(200 / 3))
    # bob: 2 games (one as winner), 1 win -> 50%
    assert stats["bob"] == (1, 50.0)
    # carol lost her only game -> 0 wins, 0% but still ranked (played a game)
    assert stats["carol"] == (0, 0.0)


def test_calculate_leaderboard_skips_games_with_no_winner():
    games = [make_game(None), make_game(None)]
    cog = ChessLeaderboard(bot=None)
    assert cog.calculate_leaderboard(games) == []


def test_calculate_leaderboard_sorts_by_wins_then_win_rate():
    # d has fewer games but a perfect win rate; more total wins should still
    # rank first, ties broken by win rate.
    games = [
        make_game("white", "a", "b"),
        make_game("white", "a", "c"),
        make_game("white", "d", "e"),
    ]
    cog = ChessLeaderboard(bot=None)
    leaderboard = cog.calculate_leaderboard(games)
    names = [name for name, _, _ in leaderboard]
    assert names[0] == "a"  # 2 wins beats d's 1 win
    assert "d" in names


def test_calculate_leaderboard_caps_at_top_5():
    games = [make_game("white", f"p{i}", f"q{i}") for i in range(10)]
    cog = ChessLeaderboard(bot=None)
    assert len(cog.calculate_leaderboard(games)) == 5


@pytest.mark.asyncio
async def test_chess_leaderboard_command_empty(leaderboard_cog, bot):
    db = MagicMock()
    db.get_chess_games = AsyncMock(return_value=[])
    bot.get_cog = Mock(return_value=db)

    ctx = mock_ctx()
    await leaderboard_cog.chess_leaderboard.callback(leaderboard_cog, ctx)

    ctx.send.assert_awaited_once_with("No games are available for the leaderboard.")
    ctx.message.add_reaction.assert_awaited_once_with("✅")


@pytest.mark.asyncio
async def test_chess_leaderboard_command_with_games(leaderboard_cog, bot):
    db = MagicMock()
    db.get_chess_games = AsyncMock(
        return_value=[make_game("white", "alice", "bob")]
    )
    bot.get_cog = Mock(return_value=db)

    ctx = mock_ctx()
    await leaderboard_cog.chess_leaderboard.callback(leaderboard_cog, ctx)

    ctx.send.assert_awaited_once()
    (kwargs) = ctx.send.call_args.kwargs
    embed = kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    assert embed.title == "Chess Leaderboard"
    assert embed.fields[0].name == "alice"
    assert "Wins: 1" in embed.fields[0].value
