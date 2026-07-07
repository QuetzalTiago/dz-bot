import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord
from discord.ext import commands

from cogs.chess import Chess


class FakeResponse:
    def __init__(self, status, json_data=None, text_data=""):
        self.status = status
        self._json = json_data or {}
        self._text = text_data

    async def json(self):
        return self._json

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    intents.message_content = True
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.fixture
def chess_cog(bot):
    cog = Chess(bot)
    cog.logger = MagicMock()
    cog.lichess_token = "test_token"
    cog.headers = {"Authorization": "Bearer test_token", "Accept": "application/json"}
    return cog


@pytest.mark.asyncio
async def test_cog_load_does_not_raise_when_lichess_token_is_not_configured(bot):
    # Regression test: this used to be `config["secrets"]["lichessToken"]`, a
    # direct index that raised KeyError (and failed the whole cog's load) on a
    # deployment without that optional key, unlike every sibling API-key cog
    # (weather/football/formula1/ufc/steam/spotify/genius/ai), which all use
    # .get(...). discord.py's Cog._inject calls cog_load() before any command
    # is registered, so a raise here silently drops the entire chess command.
    cog = Chess(bot)
    with patch("cogs.chess.load_config", return_value={"secrets": {}}):
        await cog.cog_load()
    assert cog.lichess_token is None
    assert cog.headers["Authorization"] == "Bearer None"


def mock_ctx():
    ctx = MagicMock()
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_chess_invalid_time_control(chess_cog):
    ctx = mock_ctx()
    await chess_cog.chess.callback(chess_cog, ctx, minutes=0)
    ctx.send.assert_awaited_with("Time control must be between 1 and 60 minutes.")


@pytest.mark.asyncio
async def test_chess_invalid_increment(chess_cog):
    ctx = mock_ctx()
    await chess_cog.chess.callback(chess_cog, ctx, minutes=10, increment=61)
    ctx.send.assert_awaited_with("Increment must be between 0 and 60 seconds.")


@pytest.mark.asyncio
async def test_chess_success(chess_cog):
    ctx = mock_ctx()
    with patch.object(
        chess_cog,
        "fetch_match_url",
        new=AsyncMock(return_value="https://lichess.org/abcd1234"),
    ), patch.object(chess_cog, "_watch_match", new=AsyncMock()):
        await chess_cog.chess.callback(chess_cog, ctx, minutes=10, increment=5)
    ctx.send.assert_awaited_with("https://lichess.org/abcd1234")
    ctx.message.add_reaction.assert_any_call("✅")


@pytest.mark.asyncio
async def test_chess_starts_watcher_even_if_posting_link_fails(chess_cog):
    # Regression test: the Lichess challenge already exists once fetch_match_url
    # succeeds, so a failure sending the link back to Discord must not skip
    # starting the watcher - otherwise the game's result is never posted/saved.
    ctx = mock_ctx()
    ctx.send = AsyncMock(side_effect=discord.HTTPException(Mock(status=429), "rate limited"))
    watch_match = AsyncMock()
    with patch.object(
        chess_cog,
        "fetch_match_url",
        new=AsyncMock(return_value="https://lichess.org/abcd1234"),
    ), patch.object(chess_cog, "_watch_match", new=watch_match):
        await chess_cog.chess.callback(chess_cog, ctx, minutes=10, increment=5)

    # The watcher coroutine was created (i.e. asyncio.create_task ran) even
    # though ctx.send failed - it doesn't need to finish for this assertion.
    watch_match.assert_called_once_with(ctx, "abcd1234")
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_chess_send_failure_swallows_reaction_cleanup_error(chess_cog):
    # Regression test: if clearing/reacting to the message also fails while
    # already handling a failed ctx.send, the command must not raise.
    ctx = mock_ctx()
    ctx.send = AsyncMock(side_effect=discord.HTTPException(Mock(status=429), "rate limited"))
    ctx.message.clear_reactions = AsyncMock(side_effect=discord.DiscordException("gone"))
    with patch.object(
        chess_cog,
        "fetch_match_url",
        new=AsyncMock(return_value="https://lichess.org/abcd1234"),
    ), patch.object(chess_cog, "_watch_match", new=AsyncMock()):
        await chess_cog.chess.callback(chess_cog, ctx, minutes=10, increment=5)


@pytest.mark.asyncio
async def test_chess_match_creation_failed(chess_cog):
    ctx = mock_ctx()
    with patch.object(chess_cog, "fetch_match_url", new=AsyncMock(return_value=None)):
        await chess_cog.chess.callback(chess_cog, ctx, minutes=10, increment=5)
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_fetch_match_url_success(chess_cog):
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.post = MagicMock(
        return_value=FakeResponse(200, {"url": "https://lichess.org/abcd1234"})
    )
    with patch("cogs.chess.get_session", return_value=fake_session):
        result = await chess_cog.fetch_match_url(ctx, {})
    assert result == "https://lichess.org/abcd1234"


@pytest.mark.asyncio
async def test_fetch_match_url_failure(chess_cog):
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.post = MagicMock(return_value=FakeResponse(400, text_data="Bad"))
    with patch("cogs.chess.get_session", return_value=fake_session):
        result = await chess_cog.fetch_match_url(ctx, {})
    assert result is None
    ctx.send.assert_awaited_with("There was a problem creating the challenge.")


def test_get_match_id(chess_cog):
    assert chess_cog.get_match_id("https://lichess.org/abcd1234") == "abcd1234"


def _finished_game_data(status="resign", winner="white"):
    return {
        "status": status,
        "winner": winner,
        "players": {
            "white": {"user": {"name": "alice"}},
            "black": {"user": {"name": "bob"}},
        },
    }


@pytest.mark.asyncio
async def test_watch_match_saves_and_logs_when_database_present(chess_cog):
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(200, json_data=_finished_game_data())
    )
    db = MagicMock()
    db.save_chess_game = AsyncMock()
    chess_cog.bot.get_cog = MagicMock(return_value=db)

    with patch("cogs.chess.get_session", return_value=fake_session), patch(
        "cogs.chess.asyncio.sleep", AsyncMock()
    ):
        await chess_cog._watch_match(ctx, "abcd1234")

    db.save_chess_game.assert_awaited_once()
    chess_cog.logger.info.assert_called_once()
    ctx.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_watch_match_skips_save_and_log_when_database_missing(chess_cog):
    # Regression test: the "Chess game saved" log line must not fire when the
    # Database cog isn't loaded and the game was never actually saved.
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(200, json_data=_finished_game_data())
    )
    chess_cog.bot.get_cog = MagicMock(return_value=None)

    with patch("cogs.chess.get_session", return_value=fake_session), patch(
        "cogs.chess.asyncio.sleep", AsyncMock()
    ):
        await chess_cog._watch_match(ctx, "abcd1234")

    chess_cog.logger.info.assert_not_called()
    ctx.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_watch_match_retries_on_non_200_then_saves_on_next_poll(chess_cog):
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        side_effect=[
            FakeResponse(500),
            FakeResponse(200, json_data=_finished_game_data(status="mate")),
        ]
    )
    db = MagicMock()
    db.save_chess_game = AsyncMock()
    chess_cog.bot.get_cog = MagicMock(return_value=db)

    with patch("cogs.chess.get_session", return_value=fake_session), patch(
        "cogs.chess.asyncio.sleep", AsyncMock()
    ):
        await chess_cog._watch_match(ctx, "abcd1234")

    assert fake_session.get.call_count == 2
    db.save_chess_game.assert_awaited_once()


@pytest.mark.asyncio
async def test_cog_unload_cancels_pending_watch_tasks(chess_cog):
    async def never_ending():
        await asyncio.sleep(1000)

    task = asyncio.ensure_future(never_ending())
    chess_cog._watch_tasks.add(task)

    await chess_cog.cog_unload()

    assert task.cancelled() or task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_fetch_match_url_swallows_unexpected_exception(chess_cog):
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.post = MagicMock(side_effect=RuntimeError("connection refused"))
    with patch("cogs.chess.get_session", return_value=fake_session):
        result = await chess_cog.fetch_match_url(ctx, {})
    assert result is None
    ctx.send.assert_awaited_with("An error occurred while connecting to Lichess.")
    chess_cog.logger.exception.assert_called_once()


def test_create_game_summary_embed_named_winner(chess_cog):
    embed = chess_cog.create_game_summary_embed(
        "abcd1234", "mate", "alice", "bob", "white"
    )
    assert embed.title == "alice wins!"


def test_create_game_summary_embed_anonymous_winner_uses_color(chess_cog):
    embed = chess_cog.create_game_summary_embed(
        "abcd1234", "mate", "Anonymous", "bob", "white"
    )
    assert embed.title == "White wins!"

    embed_black = chess_cog.create_game_summary_embed(
        "abcd1234", "mate", "alice", "Anonymous", "black"
    )
    assert embed_black.title == "Black wins!"


def test_create_game_summary_embed_both_anonymous_omits_names(chess_cog):
    embed = chess_cog.create_game_summary_embed(
        "abcd1234", "draw", "Anonymous", "Anonymous", None
    )
    assert "White:" not in embed.description
    assert "Black:" not in embed.description
    assert "abcd1234" in embed.description


@pytest.mark.asyncio
async def test_watch_match_continues_after_polling_exception(chess_cog):
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        side_effect=[
            RuntimeError("network blip"),
            FakeResponse(200, json_data=_finished_game_data(status="mate")),
        ]
    )
    chess_cog.bot.get_cog = MagicMock(return_value=None)

    with patch("cogs.chess.get_session", return_value=fake_session), patch(
        "cogs.chess.asyncio.sleep", AsyncMock()
    ):
        await chess_cog._watch_match(ctx, "abcd1234")

    assert fake_session.get.call_count == 2
    chess_cog.logger.exception.assert_called_once()
    ctx.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_watch_match_logs_when_posting_summary_fails(chess_cog):
    ctx = mock_ctx()
    ctx.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "rate limited"))
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(200, json_data=_finished_game_data())
    )
    chess_cog.bot.get_cog = MagicMock(return_value=None)

    with patch("cogs.chess.get_session", return_value=fake_session), patch(
        "cogs.chess.asyncio.sleep", AsyncMock()
    ):
        await chess_cog._watch_match(ctx, "abcd1234")  # must not raise

    chess_cog.logger.exception.assert_called_once()
