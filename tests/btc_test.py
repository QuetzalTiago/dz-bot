import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.btc import Btc


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    intents.message_content = True
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.fixture
def btc_cog(bot):
    return Btc(bot)


def mock_ctx():
    ctx = MagicMock()
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_btc_command_success(btc_cog):
    ctx = mock_ctx()
    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(return_value="60,000")
    ):
        with patch.object(btc_cog.btc_price_task, "is_running", return_value=True):
            await btc_cog.btc.callback(btc_cog, ctx)

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_once()
    embed = ctx.send.call_args.kwargs["embed"]
    assert "60,000" in embed.description
    assert btc_cog.sent_messages[ctx.channel.id] is ctx.send.return_value


@pytest.mark.asyncio
async def test_btc_command_starts_price_task_when_not_running(btc_cog):
    ctx = mock_ctx()
    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(return_value="60,000")
    ):
        with patch.object(
            btc_cog.btc_price_task, "is_running", return_value=False
        ), patch.object(btc_cog.btc_price_task, "start") as mock_start:
            await btc_cog.btc.callback(btc_cog, ctx)
    mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_btc_command_error(btc_cog):
    ctx = mock_ctx()
    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(side_effect=Exception("boom"))
    ):
        await btc_cog.btc.callback(btc_cog, ctx)

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_with("An error occurred while fetching the Bitcoin price.")


@pytest.mark.asyncio
async def test_btc_price_task_updates_all_channel_messages(btc_cog):
    msg_a = MagicMock()
    msg_a.edit = AsyncMock()
    msg_b = MagicMock()
    msg_b.edit = AsyncMock()
    btc_cog.sent_messages = {1: msg_a, 2: msg_b}
    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(return_value="61,000")
    ):
        await btc_cog.btc_price_task.coro(btc_cog)

    msg_a.edit.assert_awaited_once()
    msg_b.edit.assert_awaited_once()
    embed = msg_a.edit.call_args.kwargs["embed"]
    assert "61,000" in embed.description


@pytest.mark.asyncio
async def test_btc_price_task_noop_without_sent_messages(btc_cog):
    btc_cog.sent_messages = {}
    with patch.object(btc_cog, "fetch_btc_price", new=AsyncMock()) as mock_fetch:
        await btc_cog.btc_price_task.coro(btc_cog)
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_btc_price_task_swallows_fetch_errors(btc_cog):
    msg = MagicMock()
    msg.edit = AsyncMock()
    btc_cog.sent_messages = {1: msg}
    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(side_effect=Exception("boom"))
    ):
        # Should not raise even though fetch_btc_price fails.
        await btc_cog.btc_price_task.coro(btc_cog)
    msg.edit.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_btc_price_formats_amount(btc_cog):
    with patch(
        "cogs.btc.get_json",
        new=AsyncMock(return_value={"data": {"amount": "63241.5"}}),
    ):
        price = await btc_cog.fetch_btc_price()
    assert price == "63,241"


@pytest.mark.asyncio
async def test_cog_unload_cancels_task(btc_cog):
    with patch.object(btc_cog.btc_price_task, "cancel") as mock_cancel:
        await btc_cog.cog_unload()
    mock_cancel.assert_called_once()
