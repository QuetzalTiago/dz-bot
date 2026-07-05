import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.restart import Restart


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.fixture
def restart_cog(bot):
    return Restart(bot)


def mock_ctx(message_id=555, channel_id=999):
    ctx = MagicMock()
    ctx.message = MagicMock()
    ctx.message.id = message_id
    ctx.message.channel = MagicMock()
    ctx.message.channel.id = channel_id
    ctx.message.add_reaction = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_restart_success_notifies_and_closes(restart_cog):
    ctx = mock_ctx(message_id=555, channel_id=999)
    db = MagicMock()
    db.set_startup_notification = AsyncMock()
    restart_cog.bot.get_cog = MagicMock(return_value=db)
    restart_cog.bot.close = AsyncMock()

    with patch("cogs.restart.subprocess.Popen") as mock_popen:
        await restart_cog.restart.callback(restart_cog, ctx)

    mock_popen.assert_called_once_with(["aws/scripts/application-start.sh"])
    ctx.message.add_reaction.assert_awaited_once_with("⌛")
    db.set_startup_notification.assert_awaited_once_with(555, 999)
    restart_cog.bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_restart_failed_launch_does_not_persist_notification(restart_cog):
    """Regression test: a failed Popen must not leave a stale startup
    notification behind, or an unrelated later restart would react DONE to
    this failed attempt's message."""
    ctx = mock_ctx()
    db = MagicMock()
    db.set_startup_notification = AsyncMock()
    restart_cog.bot.get_cog = MagicMock(return_value=db)
    restart_cog.bot.close = AsyncMock()

    with patch("cogs.restart.subprocess.Popen", side_effect=OSError("no such file")):
        await restart_cog.restart.callback(restart_cog, ctx)

    ctx.send.assert_awaited_once_with("Failed to trigger restart.")
    db.set_startup_notification.assert_not_awaited()
    restart_cog.bot.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_restart_without_database_cog_still_closes(restart_cog):
    ctx = mock_ctx()
    restart_cog.bot.get_cog = MagicMock(return_value=None)
    restart_cog.bot.close = AsyncMock()

    with patch("cogs.restart.subprocess.Popen") as mock_popen:
        await restart_cog.restart.callback(restart_cog, ctx)

    mock_popen.assert_called_once()
    restart_cog.bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cog_setup():
    from cogs import restart

    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    await restart.setup(bot)
    bot.add_cog.assert_awaited_once()
