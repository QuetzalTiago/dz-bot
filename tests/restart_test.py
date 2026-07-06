import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from discord.ext import commands

from cogs.restart import Restart


@pytest.fixture
def mock_bot():
    return MagicMock(spec=commands.Bot)


@pytest.fixture
def restart_cog(mock_bot):
    return Restart(mock_bot)


def mock_ctx():
    ctx = MagicMock()
    ctx.message = MagicMock()
    ctx.message.id = 555
    ctx.message.channel.id = 777
    ctx.message.add_reaction = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_restart_success_notifies_db_and_closes_bot(restart_cog, mock_bot):
    ctx = mock_ctx()
    db = MagicMock()
    db.set_startup_notification = AsyncMock()
    mock_bot.get_cog.return_value = db
    mock_bot.close = AsyncMock()

    with patch("cogs.restart.subprocess.Popen") as mock_popen:
        await restart_cog.restart.callback(restart_cog, ctx)

    ctx.message.add_reaction.assert_awaited_once()
    db.set_startup_notification.assert_awaited_once_with(555, 777)
    mock_popen.assert_called_once_with(["aws/scripts/application-start.sh"])
    mock_bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_restart_without_database_cog_still_restarts(restart_cog, mock_bot):
    ctx = mock_ctx()
    mock_bot.get_cog.return_value = None
    mock_bot.close = AsyncMock()

    with patch("cogs.restart.subprocess.Popen") as mock_popen:
        await restart_cog.restart.callback(restart_cog, ctx)

    mock_popen.assert_called_once()
    mock_bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_restart_launch_failure_reports_error_and_does_not_close(
    restart_cog, mock_bot
):
    ctx = mock_ctx()
    mock_bot.get_cog.return_value = None
    mock_bot.close = AsyncMock()

    with patch("cogs.restart.subprocess.Popen", side_effect=OSError("no such file")):
        await restart_cog.restart.callback(restart_cog, ctx)

    ctx.send.assert_awaited_once_with("Failed to trigger restart.")
    mock_bot.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_restart_still_closes_bot_when_db_notification_write_fails(
    restart_cog, mock_bot
):
    # Regression test: if set_startup_notification() raises (e.g. a DB
    # connection drop) after Popen already launched the new process, the old
    # process must still close - otherwise both the old and freshly-spawned
    # process stay connected to Discord at once.
    ctx = mock_ctx()
    db = MagicMock()
    db.set_startup_notification = AsyncMock(side_effect=Exception("db gone"))
    mock_bot.get_cog.return_value = db
    mock_bot.close = AsyncMock()

    with patch("cogs.restart.subprocess.Popen") as mock_popen:
        await restart_cog.restart.callback(restart_cog, ctx)

    mock_popen.assert_called_once()
    db.set_startup_notification.assert_awaited_once()
    mock_bot.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    from cogs import restart

    await restart.setup(bot)
    bot.add_cog.assert_awaited_once()
