import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.div import Div


class FakeResponse:
    def __init__(self, status, json_data=None):
        self.status = status
        self._json = json_data or {}

    async def json(self):
        return self._json

    def raise_for_status(self):
        if self.status >= 400:
            raise Exception(f"HTTP {self.status}")

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
def div_cog(bot):
    return Div(bot)


def mock_ctx():
    ctx = MagicMock()
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


def fake_session(response):
    session = MagicMock()
    session.get = MagicMock(return_value=response)
    return session


@pytest.mark.asyncio
async def test_div_command_success(div_cog):
    ctx = mock_ctx()
    with patch.object(div_cog, "fetch_div_price", new=AsyncMock(return_value="200")):
        await div_cog.div.callback(div_cog, ctx, league="Standard")
    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_with(
        "Current Divine price in Standard league: **200 Chaos**"
    )
    ctx.message.clear_reactions.assert_awaited_once()


@pytest.mark.asyncio
async def test_div_command_no_league(div_cog):
    ctx = mock_ctx()
    await div_cog.div.callback(div_cog, ctx, league=None)
    ctx.send.assert_awaited_with("Specify the league, for example: 'div necropolis'")


@pytest.mark.asyncio
async def test_div_command_not_found(div_cog):
    ctx = mock_ctx()
    with patch.object(
        div_cog,
        "fetch_div_price",
        new=AsyncMock(side_effect=LookupError("nope")),
    ):
        await div_cog.div.callback(div_cog, ctx, league="Standard")
    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_with("Divine Orb not found for league: Standard")


@pytest.mark.asyncio
async def test_div_command_error(div_cog):
    ctx = mock_ctx()
    with patch.object(
        div_cog, "fetch_div_price", new=AsyncMock(side_effect=Exception("boom"))
    ):
        await div_cog.div.callback(div_cog, ctx, league="Standard")
    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_with(
        "Error fetching data for that league. Check the name and try again."
    )


@pytest.mark.asyncio
async def test_fetch_div_price_parses_chaos_equivalent(div_cog):
    response = FakeResponse(
        200,
        {
            "lines": [
                {"currencyTypeName": "Chaos Orb", "chaosEquivalent": 1.0},
                {"currencyTypeName": "Divine Orb", "chaosEquivalent": 187.643},
            ]
        },
    )
    with patch("cogs.div.get_session", return_value=fake_session(response)):
        price = await div_cog.fetch_div_price("Standard")
    assert price == "187"


@pytest.mark.asyncio
async def test_fetch_div_price_raises_lookup_error_when_orb_missing(div_cog):
    response = FakeResponse(200, {"lines": [{"currencyTypeName": "Chaos Orb"}]})
    with patch("cogs.div.get_session", return_value=fake_session(response)):
        with pytest.raises(LookupError):
            await div_cog.fetch_div_price("Standard")


@pytest.mark.asyncio
async def test_fetch_div_price_raises_on_http_error(div_cog):
    response = FakeResponse(404, {})
    with patch("cogs.div.get_session", return_value=fake_session(response)):
        with pytest.raises(Exception):
            await div_cog.fetch_div_price("Standard")


@pytest.mark.asyncio
async def test_div_command_uppercases_league_name(div_cog):
    ctx = mock_ctx()
    with patch.object(
        div_cog, "fetch_div_price", new=AsyncMock(return_value="200")
    ) as fetch_mock:
        await div_cog.div.callback(div_cog, ctx, league="necropolis")
    fetch_mock.assert_awaited_once_with("Necropolis")
