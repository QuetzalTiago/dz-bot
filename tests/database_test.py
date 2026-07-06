import asyncio
import datetime
import time

import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from cogs import database as database_module
from cogs.database import Database, _default_db_url
from cogs.db.base import Base


class _FakeBootstrapConn:
    """Stands in for the real MySQL bootstrap connection `_init_engine` uses
    to check/create the database - sqlite has no `SHOW DATABASES` support."""

    def execute(self, *args, **kwargs):
        result = MagicMock()
        result.fetchone.return_value = True  # pretend the database exists
        return result

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeBootstrapEngine:
    def connect(self):
        return _FakeBootstrapConn()

    def dispose(self):
        pass


@pytest.fixture
def db_cog(monkeypatch):
    # `_init_engine` hard-codes MySQL bootstrap DDL, so it can't run directly
    # against sqlite. Swap only the two `create_engine` calls it makes: the
    # bootstrap engine becomes a fake (its DB-exists-check is irrelevant
    # here), and the real engine becomes a shared in-memory sqlite one.
    # `sessionmaker` itself is left untouched so the exact kwargs `_init_engine`
    # passes it - the whole point of this regression test - are exercised for
    # real.
    real_engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    engines = iter([_FakeBootstrapEngine(), real_engine])
    monkeypatch.setattr(database_module, "create_engine", lambda *a, **k: next(engines))

    cog = Database(MagicMock(), db_url="mysql+pymysql://user:pass@host/")
    cog.db_name = "testdb"
    cog._init_engine()
    Base.metadata.create_all(cog.engine)
    return cog


CHESS_GAME = {
    "id": "abc123",
    "rated": True,
    "variant": "standard",
    "speed": "blitz",
    "perf": "blitz",
    "createdAt": 1,
    "lastMoveAt": 2,
    "status": "mate",
    "players": {
        "white": {"user": {"name": "alice"}},
        "black": {"user": {"name": "bob"}},
    },
    "winner": "white",
}


def test_init_engine_disables_expire_on_commit(db_cog):
    # Regression test: `_session()` commits and closes before `_get_*` methods
    # return their query results. A default sessionmaker (expire_on_commit=
    # True) leaves every returned entity expired *and* detached, so the very
    # first attribute access anywhere downstream (e.g. chess_leaderboard's
    # calculate_leaderboard reading `game.winner`) raised
    # sqlalchemy.orm.exc.DetachedInstanceError.
    assert db_cog.Session.kw.get("expire_on_commit") is False


@pytest.mark.asyncio
async def test_get_chess_games_returns_usable_entities_after_session_closes(db_cog):
    await db_cog.save_chess_game(CHESS_GAME)

    games = await db_cog.get_chess_games()

    assert len(games) == 1
    assert games[0].winner == "white"
    assert games[0].players["white"]["user"]["name"] == "alice"


@pytest.mark.asyncio
async def test_get_chess_games_returns_empty_list_on_error(db_cog):
    db_cog.engine.dispose()
    db_cog.Session = None  # calling Session() now raises TypeError

    games = await db_cog.get_chess_games()

    assert games == []


@pytest.mark.asyncio
async def test_update_user_durations_credits_connected_users(db_cog):
    now = datetime.datetime.now(datetime.timezone.utc)
    one_hour_ago = now - datetime.timedelta(hours=1)
    db_cog.bot.online_users = {1: one_hour_ago, 2: one_hour_ago}

    await db_cog.update_user_durations.coro(db_cog)

    hours = dict(await db_cog.get_all_user_hours())
    assert hours[1] == pytest.approx(1, abs=0.01)
    assert hours[2] == pytest.approx(1, abs=0.01)
    # The marker is reset so the next tick only credits time since now.
    assert db_cog.bot.online_users[1] > one_hour_ago
    assert db_cog.bot.online_users[2] > one_hour_ago


@pytest.mark.asyncio
async def test_update_user_durations_does_not_resurrect_user_who_disconnects_mid_tick(
    db_cog,
):
    # Regression test: a plain read of `list(online_users.items())` followed by
    # an unconditional `online_users[user_id] = now` would resurrect a user who
    # disconnected (and was popped by on_voice_state_update) while an earlier
    # user in the same tick was still being awaited - falsely marking them
    # online forever and double-crediting their voice time on every future
    # tick.
    now = datetime.datetime.now(datetime.timezone.utc)
    one_hour_ago = now - datetime.timedelta(hours=1)
    db_cog.bot.online_users = {1: one_hour_ago, 2: one_hour_ago}

    real_to_thread = database_module.asyncio.to_thread

    async def racing_to_thread(func, *args, **kwargs):
        if args and args[0] == 1:
            # Simulate user 2 disconnecting (and being flushed/popped by
            # on_voice_state_update) while user 1's flush is in flight.
            del db_cog.bot.online_users[2]
        return await real_to_thread(func, *args, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(database_module.asyncio, "to_thread", racing_to_thread)
        await db_cog.update_user_durations.coro(db_cog)

    assert 2 not in db_cog.bot.online_users
    hours = dict(await db_cog.get_all_user_hours())
    assert hours.get(2, 0) == 0
    assert hours[1] == pytest.approx(1, abs=0.01)


def test_session_rolls_back_on_error(db_cog):
    from cogs.db.entities.user import User

    with pytest.raises(Exception):
        with db_cog._session() as session:
            session.add(User(id=1))
            session.add(User(id=1))  # duplicate PK -> IntegrityError on commit

    # The failed transaction must not leave partial rows behind, and the
    # session factory must still be usable afterward.
    with db_cog._session() as session:
        assert session.query(User).count() == 0


def test_default_db_url_uses_dz_database_url_when_set(monkeypatch):
    monkeypatch.setenv("DZ_DATABASE_URL", "mysql+pymysql://custom/")
    assert _default_db_url() == "mysql+pymysql://custom/"


def test_default_db_url_assembles_from_discrete_env_vars(monkeypatch):
    monkeypatch.delenv("DZ_DATABASE_URL", raising=False)
    monkeypatch.setenv("DZ_DB_USER", "u")
    monkeypatch.setenv("DZ_DB_PASSWORD", "p")
    monkeypatch.setenv("DZ_DB_HOST", "h")
    monkeypatch.setenv("DZ_DB_PORT", "1234")

    assert _default_db_url() == "mysql+pymysql://u:p@h:1234"


@pytest.mark.asyncio
async def test_get_user_hours_for_unknown_user_returns_zero(db_cog):
    assert await db_cog.get_user_hours(999) == 0


@pytest.mark.asyncio
async def test_get_user_hours_for_known_user(db_cog):
    await db_cog.flush_user_duration(
        1, datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    )

    assert await db_cog.get_user_hours(1) == pytest.approx(2, abs=0.01)


@pytest.mark.asyncio
async def test_concurrent_flushes_for_a_brand_new_user_do_not_race(db_cog):
    # Regression test: `_update_user_duration`'s "update, insert if 0 rows"
    # upsert is a check-then-act race for a never-before-seen user_id - two
    # concurrent flushes (e.g. the hourly tick and a disconnect landing close
    # together) can both see 0 rows updated and both try to insert the same
    # new primary key, raising IntegrityError and losing one flush's credit.
    # The per-user lock in flush_user_duration/update_user_durations must
    # serialize these instead of letting both threads run at once.
    calls = []
    real_update = db_cog._update_user_duration

    def tracking_update(user_id, seconds):
        start = time.monotonic()
        time.sleep(0.05)
        real_update(user_id, seconds)
        calls.append((start, time.monotonic()))

    db_cog._update_user_duration = tracking_update

    now = datetime.datetime.now(datetime.timezone.utc)
    join_a = now - datetime.timedelta(seconds=10)
    join_b = now - datetime.timedelta(seconds=20)

    await asyncio.gather(
        db_cog.flush_user_duration(999, join_a),
        db_cog.flush_user_duration(999, join_b),
    )

    assert len(calls) == 2
    (start1, end1), (start2, end2) = sorted(calls)
    # The lock must have fully serialized the two DB calls - no overlap.
    assert start2 >= end1

    assert await db_cog.get_user_hours(999) == pytest.approx(30 / 3600, abs=0.001)


@pytest.mark.asyncio
async def test_flush_user_duration_skips_non_positive_elapsed(db_cog):
    # A join_time in the future (clock skew, or a flush racing a fresh join)
    # must not persist a negative/zero duration.
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

    await db_cog.flush_user_duration(1, future)

    assert await db_cog.get_user_hours(1) == 0


@pytest.mark.asyncio
async def test_startup_notification_round_trip(db_cog):
    assert db_cog.get_startup_notification() == (None, None)

    await db_cog.set_startup_notification(111, 222)

    assert db_cog.get_startup_notification() == ("111", "222")

    await db_cog.clear_startup_notification()

    assert db_cog.get_startup_notification() == (None, None)


@pytest.mark.asyncio
async def test_set_startup_notification_with_none_ids(db_cog):
    await db_cog.set_startup_notification(None, None)

    with db_cog._session() as session:
        from cogs.db.entities.startup_notification import StartupNotification

        notification = session.query(StartupNotification).first()
        assert notification.notify_on_startup is True
        assert notification.message_id is None
        assert notification.channel_id is None


SONG_DATA = {
    "original_url": "https://youtu.be/abc",
    "title": "Some Song",
}


@pytest.mark.asyncio
async def test_save_song_and_get_most_played_songs(db_cog):
    await db_cog.save_song(SONG_DATA, requested_by_user_id=42)
    await db_cog.save_song(SONG_DATA, requested_by_user_id=42)
    other_song = {"original_url": "https://youtu.be/xyz", "title": "Other Song"}
    await db_cog.save_song(other_song, requested_by_user_id=7)

    most_played = await db_cog.get_most_played_songs()

    assert most_played[0] == (SONG_DATA["original_url"], SONG_DATA["title"], 2)
    assert (other_song["original_url"], other_song["title"], 1) in most_played


@pytest.mark.asyncio
async def test_get_most_song_requests(db_cog):
    await db_cog.save_song(SONG_DATA, requested_by_user_id=42)
    await db_cog.save_song(SONG_DATA, requested_by_user_id=42)
    await db_cog.save_song(SONG_DATA, requested_by_user_id=7)

    requests = dict(await db_cog.get_most_song_requests())

    assert requests[42] == 2
    assert requests[7] == 1


@pytest.mark.asyncio
async def test_save_song_error_is_logged_not_raised(db_cog):
    db_cog.engine.dispose()
    db_cog.Session = None

    await db_cog.save_song(SONG_DATA, requested_by_user_id=1)  # must not raise


@pytest.mark.asyncio
async def test_get_user_data_and_delete_user_data(db_cog):
    await db_cog.flush_user_duration(
        1, datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    )
    await db_cog.save_song(SONG_DATA, requested_by_user_id=1)

    data = await db_cog.get_user_data(1)
    assert data["tracked_seconds"] > 0
    assert data["songs_requested"] == 1

    deleted = await db_cog.delete_user_data(1)
    assert deleted == 1

    cleared = await db_cog.get_user_data(1)
    assert cleared == {"tracked_seconds": 0, "songs_requested": 0}


@pytest.mark.asyncio
async def test_get_user_data_for_unknown_user(db_cog):
    data = await db_cog.get_user_data(12345)
    assert data == {"tracked_seconds": 0, "songs_requested": 0}
