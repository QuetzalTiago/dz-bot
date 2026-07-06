import pytest
from unittest.mock import AsyncMock, MagicMock

from discord.ext import commands
from discord import Embed

from cogs.chess_leaderboard import ChessLeaderboard


@pytest.fixture
def mock_bot():
    return MagicMock(spec=commands.Bot)


@pytest.fixture
def leaderboard_cog(mock_bot):
    return ChessLeaderboard(mock_bot)


def mock_ctx():
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    return ctx


def make_game(winner, white=None, black=None):
    game = MagicMock()
    game.winner = winner
    game.players = {}
    if white is not None:
        game.players["white"] = {"user": {"name": white}}
    if black is not None:
        game.players["black"] = {"user": {"name": black}}
    return game


def make_db(games):
    db = MagicMock()
    db.get_chess_games = AsyncMock(return_value=games)
    return db


def test_calculate_leaderboard_skips_games_without_winner(leaderboard_cog):
    games = [make_game(None, "alice", "bob")]
    assert leaderboard_cog.calculate_leaderboard(games) == []


def test_calculate_leaderboard_counts_wins_and_win_rate(leaderboard_cog):
    games = [
        make_game("white", "alice", "bob"),
        make_game("white", "alice", "bob"),
        make_game("black", "alice", "bob"),
    ]
    leaderboard = leaderboard_cog.calculate_leaderboard(games)

    stats = {name: (wins, rate) for name, wins, rate in leaderboard}
    assert stats["alice"] == (2, pytest.approx(200 / 3))
    assert stats["bob"] == (1, pytest.approx(100 / 3))


def test_calculate_leaderboard_ignores_missing_player_data(leaderboard_cog):
    game = make_game("white", white="alice")  # no black player recorded
    leaderboard = leaderboard_cog.calculate_leaderboard([game])
    assert leaderboard == [("alice", 1, 100.0)]


def test_calculate_leaderboard_sorts_by_wins_then_win_rate(leaderboard_cog):
    games = [
        make_game("white", "grinder", "x1"),  # grinder wins
        make_game("white", "grinder", "x2"),  # grinder wins
        make_game("black", "grinder", "x3"),  # grinder loses, x3 wins
        make_game("white", "sharp", "y1"),  # sharp wins
    ]
    leaderboard = leaderboard_cog.calculate_leaderboard(games)
    names = [name for name, _, _ in leaderboard]
    # grinder has the most wins (2); sharp and x3 are tied at 1 win / 100% rate.
    assert names[0] == "grinder"
    assert set(names[1:3]) == {"sharp", "x3"}


def test_calculate_leaderboard_top_five_cutoff(leaderboard_cog):
    games = [make_game("white", f"player{i}", f"opp{i}") for i in range(7)]
    leaderboard = leaderboard_cog.calculate_leaderboard(games)
    assert len(leaderboard) == 5


def test_get_leaderboard_embed_lists_each_player(leaderboard_cog):
    embed = leaderboard_cog.get_leaderboard_embed([("alice", 3, 75.0), ("bob", 1, 25.0)])
    assert isinstance(embed, Embed)
    assert embed.title == "Chess Leaderboard"
    assert len(embed.fields) == 2
    assert embed.fields[0].name == "alice"
    assert "Wins: 3" in embed.fields[0].value
    assert "25.00%" in embed.fields[1].value


@pytest.mark.asyncio
async def test_chess_leaderboard_command_empty(leaderboard_cog, mock_bot):
    ctx = mock_ctx()
    mock_bot.get_cog.return_value = make_db([])

    await leaderboard_cog.chess_leaderboard.callback(leaderboard_cog, ctx)

    ctx.send.assert_awaited_once_with("No games are available for the leaderboard.")
    ctx.message.add_reaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_chess_leaderboard_command_with_games(leaderboard_cog, mock_bot):
    ctx = mock_ctx()
    mock_bot.get_cog.return_value = make_db([make_game("white", "alice", "bob")])

    await leaderboard_cog.chess_leaderboard.callback(leaderboard_cog, ctx)

    mock_bot.get_cog.assert_called_with("Database")
    ctx.send.assert_awaited_once()
    _, kwargs = ctx.send.call_args
    assert isinstance(kwargs.get("embed"), Embed)
    ctx.message.add_reaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    from cogs import chess_leaderboard

    await chess_leaderboard.setup(bot)
    bot.add_cog.assert_awaited_once()
