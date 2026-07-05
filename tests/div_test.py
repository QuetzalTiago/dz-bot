import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.div import Div


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
