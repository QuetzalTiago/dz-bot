from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from cogs.btc import Btc


@pytest.fixture
def bot():
    return AsyncMock(spec=commands.Bot)


@pytest.fixture
def cog(bot):
    return Btc(bot)


def mock_ctx():
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock(spec=discord.Message)
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_btc_success_sends_embed_and_starts_task(cog):
    ctx = mock_ctx()
    price_data = {"data": {"amount": "65432.99"}}

    with patch("cogs.btc.get_json", new=AsyncMock(return_value=price_data)):
        await cog.btc.callback(cog, ctx)

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_once()
    _, kwargs = ctx.send.call_args
    embed = kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    assert "65,432" in embed.description
    assert cog.sent_message is ctx.send.return_value
    assert cog.btc_price_task.is_running()

    cog.btc_price_task.cancel()


@pytest.mark.asyncio
async def test_btc_error_reports_failure_and_does_not_send(cog):
    ctx = mock_ctx()

    with patch("cogs.btc.get_json", new=AsyncMock(side_effect=Exception("boom"))):
        await cog.btc.callback(cog, ctx)

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_once_with(
        "An error occurred while fetching the Bitcoin price."
    )
    assert cog.sent_message is None
    assert not cog.btc_price_task.is_running()


@pytest.mark.asyncio
async def test_fetch_btc_price_formats_with_thousands_separator(cog):
    with patch(
        "cogs.btc.get_json",
        new=AsyncMock(return_value={"data": {"amount": "1234567.89"}}),
    ):
        price = await cog.fetch_btc_price()

    assert price == "1,234,567"


def test_create_price_embed_contents(cog):
    embed = cog.create_price_embed("50,000")

    assert embed.title == "Bitcoin Price"
    assert "50,000 USD" in embed.description
    assert embed.footer.text == "Updated every 30 seconds"


@pytest.mark.asyncio
async def test_btc_price_task_updates_existing_message(cog):
    sent_message = AsyncMock()
    cog.sent_message = sent_message

    with patch(
        "cogs.btc.get_json", new=AsyncMock(return_value={"data": {"amount": "100"}})
    ):
        await cog.btc_price_task()

    sent_message.edit.assert_awaited_once()
    _, kwargs = sent_message.edit.call_args
    assert "100" in kwargs["embed"].description


@pytest.mark.asyncio
async def test_btc_price_task_noop_when_no_message_sent(cog):
    cog.sent_message = None

    with patch("cogs.btc.get_json", new=AsyncMock()) as mock_get_json:
        await cog.btc_price_task()

    mock_get_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_btc_price_task_swallows_errors(cog):
    cog.sent_message = AsyncMock()

    with patch(
        "cogs.btc.get_json", new=AsyncMock(side_effect=Exception("network down"))
    ):
        # Should not raise.
        await cog.btc_price_task()


@pytest.mark.asyncio
async def test_cog_unload_cancels_task(cog):
    with patch.object(cog.btc_price_task, "cancel") as mock_cancel:
        await cog.cog_unload()

    mock_cancel.assert_called_once()


@pytest.mark.asyncio
async def test_setup_adds_cog(bot):
    from cogs.btc import setup

    bot.add_cog = AsyncMock()
    await setup(bot)

    bot.add_cog.assert_awaited_once()
    added_cog = bot.add_cog.call_args[0][0]
    assert isinstance(added_cog, Btc)
