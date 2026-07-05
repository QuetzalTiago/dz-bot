import asyncio
from contextlib import suppress

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.btc import Btc


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.fixture
def btc_cog(bot):
    cog = Btc(bot)
    yield cog
    # Avoid leaking a running task loop between tests.
    if cog.btc_price_task.is_running():
        cog.btc_price_task.cancel()


def mock_ctx(channel_id=111):
    ctx = MagicMock()
    ctx.channel = MagicMock(spec=discord.TextChannel)
    ctx.channel.id = channel_id
    ctx.message = MagicMock()
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


COINBASE_RESPONSE = {"data": {"amount": "65432.10"}}


@pytest.mark.asyncio
async def test_fetch_btc_price_formats_with_thousands_separator():
    cog_bot = MagicMock()
    cog = Btc(cog_bot)
    with patch("cogs.btc.get_json", new=AsyncMock(return_value=COINBASE_RESPONSE)):
        price = await cog.fetch_btc_price()
    assert price == "65,432"


def test_create_price_embed_contains_price(btc_cog):
    embed = btc_cog.create_price_embed("65,432")
    assert "65,432" in embed.description
    assert embed.title == "Bitcoin Price"


@pytest.mark.asyncio
async def test_btc_command_success_sends_embed_and_tracks_message(btc_cog):
    ctx = mock_ctx(channel_id=111)
    sent_message = MagicMock()
    ctx.send.return_value = sent_message

    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(return_value="65,432")
    ):
        await btc_cog.btc.callback(btc_cog, ctx)

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_once()
    assert btc_cog.sent_messages[111] is sent_message
    assert btc_cog.btc_price_task.is_running()


@pytest.mark.asyncio
async def test_btc_command_error_does_not_track_message(btc_cog):
    ctx = mock_ctx(channel_id=222)

    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(side_effect=Exception("boom"))
    ):
        await btc_cog.btc.callback(btc_cog, ctx)

    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_with("An error occurred while fetching the Bitcoin price.")
    assert 222 not in btc_cog.sent_messages
    assert not btc_cog.btc_price_task.is_running()


@pytest.mark.asyncio
async def test_btc_command_tracks_multiple_channels_independently(btc_cog):
    ctx_a = mock_ctx(channel_id=1)
    ctx_a.send.return_value = MagicMock(name="message_a")
    ctx_b = mock_ctx(channel_id=2)
    ctx_b.send.return_value = MagicMock(name="message_b")

    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(return_value="1,000")
    ):
        await btc_cog.btc.callback(btc_cog, ctx_a)
        await btc_cog.btc.callback(btc_cog, ctx_b)

    # Regression test: previously a single shared `sent_message` attribute
    # meant the second channel's invocation silently stopped the first
    # channel's ticker from ever being updated again.
    assert btc_cog.sent_messages[1] is ctx_a.send.return_value
    assert btc_cog.sent_messages[2] is ctx_b.send.return_value
    assert len(btc_cog.sent_messages) == 2


@pytest.mark.asyncio
async def test_price_task_updates_every_tracked_message(btc_cog):
    msg_a = AsyncMock()
    msg_b = AsyncMock()
    btc_cog.sent_messages = {1: msg_a, 2: msg_b}

    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(return_value="1,000")
    ):
        await btc_cog.btc_price_task.coro(btc_cog)

    msg_a.edit.assert_awaited_once()
    msg_b.edit.assert_awaited_once()
    assert set(btc_cog.sent_messages) == {1, 2}


@pytest.mark.asyncio
async def test_price_task_drops_message_that_fails_to_edit(btc_cog):
    healthy = AsyncMock()
    broken = AsyncMock()
    broken.edit.side_effect = discord.NotFound(MagicMock(status=404), "unknown message")
    btc_cog.sent_messages = {1: healthy, 2: broken}

    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(return_value="1,000")
    ):
        await btc_cog.btc_price_task.coro(btc_cog)

    # The broken channel is dropped so the loop stops retrying it forever,
    # but the healthy channel keeps getting updated.
    assert 2 not in btc_cog.sent_messages
    assert 1 in btc_cog.sent_messages
    healthy.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_price_task_noop_when_no_messages_tracked(btc_cog):
    with patch("cogs.btc.get_json", new=AsyncMock()) as mocked_get_json:
        await btc_cog.btc_price_task.coro(btc_cog)
    mocked_get_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_price_task_survives_fetch_failure(btc_cog):
    msg = AsyncMock()
    btc_cog.sent_messages = {1: msg}

    with patch.object(
        btc_cog, "fetch_btc_price", new=AsyncMock(side_effect=Exception("network down"))
    ):
        await btc_cog.btc_price_task.coro(btc_cog)

    msg.edit.assert_not_awaited()
    assert 1 in btc_cog.sent_messages


@pytest.mark.asyncio
async def test_cog_unload_cancels_task(btc_cog):
    btc_cog.btc_price_task.start()
    assert btc_cog.btc_price_task.is_running()
    task = btc_cog.btc_price_task.get_task()

    await btc_cog.cog_unload()
    with suppress(asyncio.CancelledError):
        await task

    assert not btc_cog.btc_price_task.is_running()


@pytest.mark.asyncio
async def test_cog_setup(monkeypatch):
    from cogs import btc

    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    await btc.setup(bot)
    bot.add_cog.assert_awaited_once()
