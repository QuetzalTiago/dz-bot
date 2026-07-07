import pytest
from unittest.mock import AsyncMock, MagicMock

from discord.ext import commands

from cogs.privacy import Privacy


@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=commands.Bot)
    bot.online_users = {}
    return bot


@pytest.fixture
def privacy_cog(mock_bot):
    return Privacy(mock_bot)


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.author.id = 123
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_my_data_reports_tracked_hours_and_songs(privacy_cog, mock_bot, mock_ctx):
    db = MagicMock()
    db.get_user_data = AsyncMock(
        return_value={"tracked_seconds": 7200, "songs_requested": 4}
    )
    mock_bot.get_cog.return_value = db

    await privacy_cog.my_data.callback(privacy_cog, mock_ctx)

    db.get_user_data.assert_awaited_once_with(123)
    mock_ctx.send.assert_awaited_once()
    embed = mock_ctx.send.await_args.kwargs["embed"]
    assert embed.fields[0].value == "2.0 hours"
    assert embed.fields[1].value == "4"


@pytest.mark.asyncio
async def test_my_data_reports_error_and_reacts_error_when_db_raises(
    privacy_cog, mock_bot, mock_ctx
):
    # Regression test: same bug class as status.py/leaderboard.py - an
    # unhandled DB error must not leave the before_invoke ACK reaction stuck
    # with no error indicator.
    mock_ctx.message.clear_reactions = AsyncMock()
    mock_ctx.message.add_reaction = AsyncMock()
    db = MagicMock()
    db.get_user_data = AsyncMock(side_effect=RuntimeError("db down"))
    mock_bot.get_cog.return_value = db

    await privacy_cog.my_data.callback(privacy_cog, mock_ctx)

    mock_ctx.send.assert_awaited_once_with("Something went wrong fetching your data.")
    mock_ctx.message.clear_reactions.assert_awaited_once()
    mock_ctx.message.add_reaction.assert_awaited_once_with("❌")


@pytest.mark.asyncio
async def test_my_data_when_database_unavailable(privacy_cog, mock_bot, mock_ctx):
    mock_bot.get_cog.return_value = None

    await privacy_cog.my_data.callback(privacy_cog, mock_ctx)

    mock_ctx.send.assert_awaited_once_with("Data storage is not available right now.")


@pytest.mark.asyncio
async def test_forget_me_erases_data_and_in_memory_tracking(
    privacy_cog, mock_bot, mock_ctx
):
    db = MagicMock()
    db.delete_user_data = AsyncMock()
    mock_bot.get_cog.return_value = db
    # online_users is keyed by (guild_id, user_id) - the same user (123) can
    # be tracked in more than one guild at once, and both must be cleared.
    mock_bot.online_users = {
        (1, 123): "some-join-time",
        (2, 123): "other-guild-join-time",
        (1, 456): "other-user",
    }

    await privacy_cog.forget_me.callback(privacy_cog, mock_ctx)

    db.delete_user_data.assert_awaited_once_with(123)
    assert (1, 123) not in mock_bot.online_users
    assert (2, 123) not in mock_bot.online_users
    assert (1, 456) in mock_bot.online_users
    mock_ctx.send.assert_awaited_once_with("Your stored data has been erased.")


@pytest.mark.asyncio
async def test_forget_me_drops_online_tracking_before_deleting_from_db(
    privacy_cog, mock_bot, mock_ctx
):
    # Regression test: online_users must be popped *before* delete_user_data
    # is awaited, not after - otherwise the hourly duration flush (or this
    # same user disconnecting) can race the delete and re-insert a row for a
    # user who just asked to have their data erased.
    call_order = []

    async def fake_delete(user_id):
        call_order.append(("delete_user_data", dict(mock_bot.online_users)))

    db = MagicMock()
    db.delete_user_data = fake_delete
    mock_bot.get_cog.return_value = db
    mock_bot.online_users = {(1, 123): "some-join-time"}

    await privacy_cog.forget_me.callback(privacy_cog, mock_ctx)

    # By the time delete_user_data ran, the user was already gone from
    # online_users.
    assert call_order == [("delete_user_data", {})]


@pytest.mark.asyncio
async def test_forget_me_reports_error_and_reacts_error_when_db_raises(
    privacy_cog, mock_bot, mock_ctx
):
    # Regression test: same bug class already fixed for my_data() - an
    # unhandled DB error must not leave the before_invoke ACK reaction stuck
    # with no error indicator. forget_me() was the one sibling command in
    # this file that was missed by that earlier fix.
    mock_ctx.message.clear_reactions = AsyncMock()
    mock_ctx.message.add_reaction = AsyncMock()
    db = MagicMock()
    db.delete_user_data = AsyncMock(side_effect=RuntimeError("db down"))
    mock_bot.get_cog.return_value = db
    mock_bot.online_users = {}

    await privacy_cog.forget_me.callback(privacy_cog, mock_ctx)

    mock_ctx.send.assert_awaited_once_with("Something went wrong erasing your data.")
    mock_ctx.message.clear_reactions.assert_awaited_once()
    mock_ctx.message.add_reaction.assert_awaited_once_with("❌")


@pytest.mark.asyncio
async def test_forget_me_when_database_unavailable(privacy_cog, mock_bot, mock_ctx):
    mock_bot.get_cog.return_value = None

    await privacy_cog.forget_me.callback(privacy_cog, mock_ctx)

    mock_ctx.send.assert_awaited_once_with("Data storage is not available right now.")


@pytest.mark.asyncio
async def test_forget_me_when_user_not_in_online_users(privacy_cog, mock_bot, mock_ctx):
    db = MagicMock()
    db.delete_user_data = AsyncMock()
    mock_bot.get_cog.return_value = db
    mock_bot.online_users = {}

    await privacy_cog.forget_me.callback(privacy_cog, mock_ctx)

    mock_ctx.send.assert_awaited_once_with("Your stored data has been erased.")


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    from cogs import privacy

    await privacy.setup(bot)
    bot.add_cog.assert_awaited_once()
