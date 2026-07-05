import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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
