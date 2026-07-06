import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from cogs import database as database_module
from cogs.database import Database
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
