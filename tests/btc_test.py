import asyncio
import contextlib

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from discord.ext import commands
from discord import Embed

from cogs.btc import Btc


@pytest.fixture
def mock_bot():
    return MagicMock(spec=commands.Bot)


@pytest.fixture
def btc_cog(mock_bot):
    return Btc(mock_bot)


async def cancel_and_wait(loop_task):
    """Cancel a running tasks.loop and let it actually finish, so it doesn't
    outlive the test's event loop."""
    loop_task.cancel()
    task = loop_task.get_task()
    if task is not None:
        with contextlib.suppress(asyncio.CancelledError):
            await task


def mock_ctx():
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_fetch_btc_price_formats_with_thousands_separator(btc_cog):
    with patch("cogs.btc.get_json", new=AsyncMock(return_value={"data": {"amount": "65432.10"}})):
        price = await btc_cog.fetch_btc_price()
    assert price == "65,432"


def test_create_price_embed(btc_cog):
    embed = btc_cog.create_price_embed("65,432")
    assert isinstance(embed, Embed)
    assert embed.title == "Bitcoin Price"
    assert "65,432 USD" in embed.description


@pytest.mark.asyncio
async def test_btc_command_success_starts_price_task(btc_cog):
    ctx = mock_ctx()
    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(return_value="10,000")
    ):
        await btc_cog.btc.callback(btc_cog, ctx)

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_once()
    _, kwargs = ctx.send.call_args
    assert isinstance(kwargs.get("embed"), Embed)
    assert btc_cog.sent_message is ctx.send.return_value
    assert btc_cog.btc_price_task.is_running()
    await cancel_and_wait(btc_cog.btc_price_task)


@pytest.mark.asyncio
async def test_btc_command_error(btc_cog):
    ctx = mock_ctx()
    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(side_effect=Exception("boom"))
    ):
        await btc_cog.btc.callback(btc_cog, ctx)

    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_once_with(
        "An error occurred while fetching the Bitcoin price."
    )
    assert not btc_cog.btc_price_task.is_running()


@pytest.mark.asyncio
async def test_price_task_noop_without_sent_message(btc_cog):
    assert btc_cog.sent_message is None
    await btc_cog.btc_price_task.coro(btc_cog)  # should not raise


@pytest.mark.asyncio
async def test_price_task_updates_sent_message(btc_cog):
    btc_cog.sent_message = MagicMock()
    btc_cog.sent_message.edit = AsyncMock()
    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(return_value="20,000")
    ):
        await btc_cog.btc_price_task.coro(btc_cog)

    btc_cog.sent_message.edit.assert_awaited_once()
    _, kwargs = btc_cog.sent_message.edit.call_args
    assert isinstance(kwargs.get("embed"), Embed)


@pytest.mark.asyncio
async def test_price_task_swallows_errors(btc_cog):
    btc_cog.sent_message = MagicMock()
    btc_cog.sent_message.edit = AsyncMock()
    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(side_effect=Exception("boom"))
    ):
        await btc_cog.btc_price_task.coro(btc_cog)  # should not raise

    btc_cog.sent_message.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_before_btc_price_task_waits_until_ready(btc_cog, mock_bot):
    mock_bot.wait_until_ready = AsyncMock()
    await btc_cog.before_btc_price_task()
    mock_bot.wait_until_ready.assert_awaited_once()


@pytest.mark.asyncio
async def test_cog_unload_cancels_task(btc_cog):
    btc_cog.btc_price_task.start()
    task = btc_cog.btc_price_task.get_task()
    await btc_cog.cog_unload()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert not btc_cog.btc_price_task.is_running()


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    from cogs import btc

    await btc.setup(bot)
    bot.add_cog.assert_awaited_once()
