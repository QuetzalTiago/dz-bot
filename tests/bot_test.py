import logging
import logging.handlers
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

import bot as bot_module
from bot import Khaled, _configure_logging, _init_observability, _load_owner_ids


def _set_connection_state(khaled, user=None, guilds=None):
    """discord.py's Client.user/.guilds are read-only properties proxying
    self._connection - swap the whole connection state to stub them."""
    conn = MagicMock()
    conn.user = user
    conn.guilds = guilds if guilds is not None else []
    khaled._connection = conn


def _param_mock(name):
    param = MagicMock()
    param.name = name
    param.displayed_name = None
    return param


@pytest.fixture
def khaled():
    intents = discord.Intents.default()
    return Khaled(command_prefix="!", intents=intents, initial_extensions=[])


def test_configure_logging_defaults_to_info(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DZ_LOG_LEVEL", raising=False)
    logger = _configure_logging()
    try:
        assert logger.level == logging.INFO
        assert any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            for h in logger.handlers
        )
    finally:
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()


def test_configure_logging_honors_env_level(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DZ_LOG_LEVEL", "DEBUG")
    logger = _configure_logging()
    try:
        assert logger.level == logging.DEBUG
    finally:
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()


def test_load_owner_ids_merges_config_and_env(monkeypatch):
    logger = MagicMock()
    monkeypatch.setenv("DZ_OWNERS", "222, 333,,")
    owner_ids = _load_owner_ids({"owners": [111, "444"]}, logger)
    assert owner_ids == {111, 444, 222, 333}
    logger.warning.assert_not_called()


def test_load_owner_ids_ignores_invalid_entries(monkeypatch):
    logger = MagicMock()
    monkeypatch.setenv("DZ_OWNERS", "not-a-number")
    owner_ids = _load_owner_ids({"owners": [111, "bogus", None]}, logger)
    assert owner_ids == {111}
    # "bogus" (config), None (config), and "not-a-number" (DZ_OWNERS) each warn.
    assert logger.warning.call_count == 3


def test_load_owner_ids_empty_when_unset(monkeypatch):
    monkeypatch.delenv("DZ_OWNERS", raising=False)
    assert _load_owner_ids({}, MagicMock()) == set()


def test_init_observability_noop_without_dsn(monkeypatch):
    monkeypatch.delenv("DZ_SENTRY_DSN", raising=False)
    logger = MagicMock()
    _init_observability(logger)
    logger.info.assert_not_called()
    logger.warning.assert_not_called()


def test_init_observability_warns_when_sentry_missing(monkeypatch):
    monkeypatch.setenv("DZ_SENTRY_DSN", "https://example.invalid/1")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    logger = MagicMock()
    _init_observability(logger)
    logger.warning.assert_called_once()


def test_init_observability_initializes_sentry_when_available(monkeypatch):
    fake_sentry = MagicMock()
    monkeypatch.setenv("DZ_SENTRY_DSN", "https://example.invalid/1")
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    logger = MagicMock()
    _init_observability(logger)
    fake_sentry.init.assert_called_once_with(
        dsn="https://example.invalid/1", traces_sample_rate=0.0
    )
    logger.info.assert_called_once()


@pytest.mark.asyncio
async def test_setup_hook_loads_extensions_and_syncs_tree(khaled):
    khaled.initial_extensions = ["cogs.a", "cogs.b"]
    khaled.load_extension = AsyncMock()
    khaled.tree.sync = AsyncMock()

    await khaled.setup_hook()

    assert khaled.load_extension.await_args_list == [
        ((("cogs.a",)),),
        ((("cogs.b",)),),
    ]
    khaled.tree.sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_hook_survives_extension_and_sync_failures(khaled):
    khaled.initial_extensions = ["cogs.broken"]
    khaled.load_extension = AsyncMock(side_effect=Exception("boom"))
    khaled.tree.sync = AsyncMock(side_effect=RuntimeError("nope"))

    # Must not raise even though both the extension load and the tree sync fail.
    await khaled.setup_hook()


@pytest.mark.asyncio
async def test_close_closes_shared_session_and_super(khaled, monkeypatch):
    close_session_mock = AsyncMock()
    monkeypatch.setattr(bot_module, "close_session", close_session_mock)
    super_close = AsyncMock()
    monkeypatch.setattr(commands.AutoShardedBot, "close", super_close)

    await khaled.close()

    close_session_mock.assert_awaited_once()
    super_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_ready_starts_btc_task_and_skips_missing_database(khaled):
    _set_connection_state(khaled, user=MagicMock(id=1))
    btc_cog = MagicMock()
    btc_cog.btc_price_task.is_running.return_value = False
    btc_cog.btc_price_task.start = MagicMock()

    def get_cog(name):
        return {"Btc": btc_cog, "Database": None}.get(name)

    khaled.get_cog = MagicMock(side_effect=get_cog)
    khaled.change_presence = AsyncMock()
    khaled.update_online_users = AsyncMock()

    await khaled.on_ready()

    btc_cog.btc_price_task.start.assert_called_once()
    khaled.change_presence.assert_awaited_once()
    khaled.update_online_users.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_ready_does_not_restart_running_btc_task(khaled):
    _set_connection_state(khaled, user=MagicMock(id=1))
    btc_cog = MagicMock()
    btc_cog.btc_price_task.is_running.return_value = True

    khaled.get_cog = MagicMock(side_effect=lambda name: {"Btc": btc_cog}.get(name))
    khaled.change_presence = AsyncMock()
    khaled.update_online_users = AsyncMock()

    await khaled.on_ready()

    btc_cog.btc_price_task.start.assert_not_called()


@pytest.mark.asyncio
async def test_on_ready_resolves_startup_notification(khaled):
    _set_connection_state(khaled, user=MagicMock(id=1))
    db_cog = MagicMock()
    db_cog.get_startup_notification = MagicMock(return_value=(555, 777))
    db_cog.clear_startup_notification = AsyncMock()

    khaled.get_cog = MagicMock(side_effect=lambda name: {"Database": db_cog}.get(name))
    khaled.change_presence = AsyncMock()
    khaled.update_online_users = AsyncMock()
    fake_message = MagicMock()
    fake_message.clear_reactions = AsyncMock()
    fake_message.add_reaction = AsyncMock()
    khaled.fetch_message_by_id = AsyncMock(return_value=fake_message)

    await khaled.on_ready()

    khaled.fetch_message_by_id.assert_awaited_once_with(777, 555)
    fake_message.clear_reactions.assert_awaited_once()
    fake_message.add_reaction.assert_awaited_once()
    db_cog.clear_startup_notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_ready_skips_notification_when_none_pending(khaled):
    _set_connection_state(khaled, user=MagicMock(id=1))
    db_cog = MagicMock()
    db_cog.get_startup_notification = MagicMock(return_value=(None, None))

    khaled.get_cog = MagicMock(side_effect=lambda name: {"Database": db_cog}.get(name))
    khaled.change_presence = AsyncMock()
    khaled.update_online_users = AsyncMock()
    khaled.fetch_message_by_id = AsyncMock()

    await khaled.on_ready()

    khaled.fetch_message_by_id.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error, expected_snippet",
    [
        (commands.CheckFailure("nope"), "nope"),
        (
            commands.CommandOnCooldown(
                commands.Cooldown(1, 5), 2.5, commands.BucketType.user
            ),
            "cooldown",
        ),
        (
            commands.MissingRequiredArgument(_param_mock("city")),
            "Missing argument",
        ),
        (commands.UserInputError("bad input"), "Invalid input"),
    ],
)
async def test_on_command_error_sends_user_facing_message(khaled, error, expected_snippet):
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.command = MagicMock(name="somecmd")

    await khaled.on_command_error(ctx, error)

    ctx.send.assert_awaited_once()
    assert expected_snippet in ctx.send.await_args.args[0]


@pytest.mark.asyncio
async def test_on_command_error_ignores_command_not_found(khaled):
    ctx = MagicMock()
    ctx.send = AsyncMock()

    await khaled.on_command_error(ctx, commands.CommandNotFound())

    ctx.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_command_error_logs_and_sends_generic_message_for_unknown_errors(khaled):
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.command = MagicMock()
    ctx.command.name = "somecmd"
    khaled.logger = MagicMock()

    await khaled.on_command_error(ctx, RuntimeError("kaboom"))

    khaled.logger.exception.assert_called_once()
    ctx.send.assert_awaited_once_with("Something went wrong while running that command.")


@pytest.mark.asyncio
async def test_on_command_error_swallows_send_failure(khaled):
    # If the channel/command context is already gone (e.g. concurrent purge),
    # ctx.send raising must not propagate out of the error handler itself.
    ctx = MagicMock()
    ctx.send = AsyncMock(side_effect=discord.DiscordException("channel gone"))
    ctx.command = MagicMock()
    ctx.command.name = "somecmd"
    khaled.logger = MagicMock()

    await khaled.on_command_error(ctx, RuntimeError("kaboom"))  # must not raise

    ctx.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_online_users_tracks_humans_not_bots_and_does_not_reset_join_time(
    khaled,
):
    human = MagicMock(id=1, bot=False)
    bot_member = MagicMock(id=2, bot=True)
    voice_channel = MagicMock(members=[human, bot_member])
    guild = MagicMock(id=100, voice_channels=[voice_channel])
    _set_connection_state(khaled, guilds=[guild])

    sentinel_join_time = object()
    khaled.online_users = {(100, 1): sentinel_join_time}

    await khaled.update_online_users()

    # Existing join time for a member already being tracked must survive a
    # second on_ready (reconnect) firing - setdefault, not overwrite.
    assert khaled.online_users[(100, 1)] is sentinel_join_time
    assert (100, 2) not in khaled.online_users


@pytest.mark.asyncio
async def test_on_voice_state_update_disconnect_flushes_duration(khaled):
    member = MagicMock(id=42, guild=MagicMock(id=100))
    before = MagicMock(channel=MagicMock())
    after = MagicMock(channel=None)
    join_time = object()
    khaled.online_users = {(100, 42): join_time}

    db_cog = MagicMock()
    db_cog.flush_user_duration = AsyncMock()
    khaled.get_cog = MagicMock(side_effect=lambda name: {"Database": db_cog}.get(name))
    _set_connection_state(khaled, user=MagicMock(id=999))

    await khaled.on_voice_state_update(member, before, after)

    assert (100, 42) not in khaled.online_users
    db_cog.flush_user_duration.assert_awaited_once_with(42, join_time)


@pytest.mark.asyncio
async def test_on_voice_state_update_disconnect_from_one_guild_keeps_other_guild_session(
    khaled,
):
    # Regression test: online_users is keyed by (guild_id, member_id) - the
    # same user connected in two guilds at once must not have one guild's
    # disconnect wipe out the other guild's still-active session.
    member = MagicMock(id=42, guild=MagicMock(id=100))
    before = MagicMock(channel=MagicMock())
    after = MagicMock(channel=None)
    other_guild_join_time = object()
    khaled.online_users = {
        (100, 42): object(),
        (200, 42): other_guild_join_time,
    }

    db_cog = MagicMock()
    db_cog.flush_user_duration = AsyncMock()
    khaled.get_cog = MagicMock(side_effect=lambda name: {"Database": db_cog}.get(name))
    _set_connection_state(khaled, user=MagicMock(id=999))

    await khaled.on_voice_state_update(member, before, after)

    assert (100, 42) not in khaled.online_users
    assert khaled.online_users[(200, 42)] is other_guild_join_time


@pytest.mark.asyncio
async def test_on_voice_state_update_connect_tracks_human_join(khaled):
    member = MagicMock(id=7, bot=False, guild=MagicMock(id=100))
    before = MagicMock(channel=None)
    after = MagicMock(channel=MagicMock())
    khaled.online_users = {}
    khaled.get_cog = MagicMock(return_value=None)
    _set_connection_state(khaled, user=MagicMock(id=999))

    await khaled.on_voice_state_update(member, before, after)

    assert (100, 7) in khaled.online_users


@pytest.mark.asyncio
async def test_on_voice_state_update_bot_kicked_triggers_forced_disconnect(khaled):
    guild = MagicMock()
    before_channel = MagicMock(guild=guild)
    member = MagicMock(id=999)
    before = MagicMock(channel=before_channel)
    after = MagicMock(channel=None)

    music_cog = MagicMock()
    music_cog.handle_forced_disconnect = AsyncMock()
    khaled.get_cog = MagicMock(side_effect=lambda name: {"Music": music_cog}.get(name))
    _set_connection_state(khaled, user=MagicMock(id=999))
    khaled.online_users = {}

    await khaled.on_voice_state_update(member, before, after)

    music_cog.handle_forced_disconnect.assert_awaited_once_with(guild)


@pytest.mark.asyncio
async def test_fetch_message_by_id_rejects_non_integer_ids(khaled):
    assert await khaled.fetch_message_by_id("abc", "def") is None


@pytest.mark.asyncio
async def test_fetch_message_by_id_returns_none_when_channel_missing(khaled):
    khaled.get_channel = MagicMock(return_value=None)
    assert await khaled.fetch_message_by_id(123, 456) is None


@pytest.mark.asyncio
async def test_fetch_message_by_id_returns_message_on_success(khaled):
    channel = MagicMock()
    fake_message = MagicMock()
    channel.fetch_message = AsyncMock(return_value=fake_message)
    khaled.get_channel = MagicMock(return_value=channel)

    result = await khaled.fetch_message_by_id(123, 456)

    assert result is fake_message
    channel.fetch_message.assert_awaited_once_with(456)


@pytest.mark.asyncio
async def test_fetch_message_by_id_returns_none_on_discord_exception(khaled):
    channel = MagicMock()
    channel.fetch_message = AsyncMock(side_effect=discord.DiscordException("nope"))
    khaled.get_channel = MagicMock(return_value=channel)

    assert await khaled.fetch_message_by_id(123, 456) is None
