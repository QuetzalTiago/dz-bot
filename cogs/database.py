import asyncio
import datetime
import logging
import os
from contextlib import contextmanager

from discord.ext import commands, tasks
from sqlalchemy import create_engine, func, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from cogs.db.base import Base
from cogs.db.entities.btc_price import BitcoinPrice
from cogs.db.entities.chess_game import ChessGame
from cogs.db.entities.song import Song
from cogs.db.entities.startup_notification import StartupNotification
from cogs.db.entities.user import User


def _default_db_url() -> str:
    """Build the DB URL from the environment.

    Credentials are no longer hardcoded. ``DZ_DATABASE_URL`` (minus the
    database name) takes precedence; otherwise the pieces are assembled from
    discrete env vars with non-root defaults for local development.
    """
    url = os.environ.get("DZ_DATABASE_URL")
    if url:
        return url
    user = os.environ.get("DZ_DB_USER", "dzbot")
    password = os.environ.get("DZ_DB_PASSWORD", "dzbot")
    host = os.environ.get("DZ_DB_HOST", "db")
    port = os.environ.get("DZ_DB_PORT", "3306")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}"


class Database(commands.Cog):
    def __init__(self, bot, db_url=None):
        self.bot = bot
        self.db_url = db_url or _default_db_url()
        self.db_name = os.environ.get("DZ_DB_NAME", "discord_bot")
        self.engine = None
        self.Session = None
        self.logger = logging.getLogger("discord")

    async def cog_load(self):
        # Blocking DB setup is offloaded so it never stalls the event loop.
        await asyncio.to_thread(self._init_engine)
        # Start the periodic flush only after the session factory exists.
        self.update_user_durations.start()

    async def cog_unload(self):
        self.update_user_durations.cancel()

    def _init_engine(self):
        # Connect without a database to ensure it exists, then reconnect to it.
        bootstrap_engine = create_engine(self.db_url)
        # Validate the identifier since it flows into a DDL statement.
        if not self.db_name.isidentifier():
            raise ValueError(f"Invalid database name: {self.db_name!r}")
        with bootstrap_engine.connect() as conn:
            exists = conn.execute(
                text("SHOW DATABASES LIKE :name"), {"name": self.db_name}
            ).fetchone()
            if not exists:
                conn.execute(text(f"CREATE DATABASE `{self.db_name}`"))
                conn.commit()
                self.logger.info("Database %s created.", self.db_name)
        bootstrap_engine.dispose()

        url = make_url(self.db_url).set(database=self.db_name)
        self.engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
        # expire_on_commit=False: _session() commits and closes before
        # returning, so a default sessionmaker would leave every returned
        # entity expired and detached — the next attribute access (e.g.
        # game.winner in chess_leaderboard) raises DetachedInstanceError.
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        self.logger.info("DB connection initialized")

    @contextmanager
    def _session(self):
        """Session scope that always commits/rolls back and closes."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ---- Voice-time tracking -------------------------------------------------

    @tasks.loop(hours=1)
    async def update_user_durations(self):
        """Flush accrued voice time for everyone currently connected.

        Each tick credits only the time elapsed *since the last flush* and
        resets the marker, so a user online for N hours is credited N hours
        (the old code re-added the full elapsed time every hour).
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        for user_id, join_time in list(self.bot.online_users.items()):
            seconds = int((now - join_time).total_seconds())
            if seconds <= 0:
                continue
            self.bot.online_users[user_id] = now
            try:
                await asyncio.to_thread(self._update_user_duration, user_id, seconds)
            except Exception:
                self.logger.exception("Failed to update duration for %s", user_id)

    @update_user_durations.before_loop
    async def _before_durations(self):
        await self.bot.wait_until_ready()

    @update_user_durations.error
    async def _durations_error(self, error):
        self.logger.exception("update_user_durations loop errored", exc_info=error)

    def _update_user_duration(self, user_id, additional_seconds):
        with self._session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user is None:
                session.add(
                    User(id=user_id, total_duration_seconds=additional_seconds)
                )
            else:
                user.total_duration_seconds += additional_seconds

    async def flush_user_duration(self, user_id, join_time):
        """Persist a single user's accrued time (called on disconnect)."""
        seconds = int(
            (datetime.datetime.now(datetime.timezone.utc) - join_time).total_seconds()
        )
        if seconds > 0:
            await asyncio.to_thread(self._update_user_duration, user_id, seconds)

    async def get_user_hours(self, user_id):
        return await asyncio.to_thread(self._get_user_hours, user_id)

    def _get_user_hours(self, user_id):
        with self._session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            return user.total_duration_seconds / 3600 if user else 0

    async def get_all_user_hours(self):
        return await asyncio.to_thread(self._get_all_user_hours)

    def _get_all_user_hours(self):
        with self._session() as session:
            users = session.query(User.id, User.total_duration_seconds).all()
            return [(uid, secs / 3600) for uid, secs in users]

    # ---- Chess ---------------------------------------------------------------

    async def save_chess_game(self, game_data):
        try:
            await asyncio.to_thread(self._save_chess_game, game_data)
        except Exception:
            self.logger.exception("Error saving chess game")

    def _save_chess_game(self, game_data):
        with self._session() as session:
            session.add(ChessGame(game_data))

    async def get_chess_games(self):
        try:
            return await asyncio.to_thread(self._get_chess_games)
        except Exception:
            self.logger.exception("Error fetching chess games")
            return []

    def _get_chess_games(self):
        with self._session() as session:
            return session.query(ChessGame).all()

    # ---- Startup notification ------------------------------------------------

    async def set_startup_notification(self, message_id, channel_id):
        await asyncio.to_thread(self._set_startup_notification, message_id, channel_id)

    def _set_startup_notification(self, message_id, channel_id):
        with self._session() as session:
            notification = session.query(StartupNotification).first()
            if not notification:
                notification = StartupNotification()
                session.add(notification)
            notification.notify_on_startup = True
            notification.message_id = str(message_id) if message_id else None
            notification.channel_id = str(channel_id) if channel_id else None

    async def clear_startup_notification(self):
        await asyncio.to_thread(self._clear_startup_notification)

    def _clear_startup_notification(self):
        with self._session() as session:
            notification = session.query(StartupNotification).first()
            if notification:
                notification.notify_on_startup = False
                notification.message_id = None
                notification.channel_id = None

    def get_startup_notification(self):
        """Synchronous read used once during on_ready (before commands run)."""
        with self._session() as session:
            notification = session.query(StartupNotification).first()
            if notification and notification.notify_on_startup:
                return notification.message_id, notification.channel_id
            return None, None

    # ---- Bitcoin -------------------------------------------------------------

    async def update_bitcoin_price(self, new_price):
        try:
            await asyncio.to_thread(self._update_bitcoin_price, new_price)
        except Exception:
            self.logger.exception("Error updating Bitcoin price")

    def _update_bitcoin_price(self, new_price):
        with self._session() as session:
            btc_price = session.query(BitcoinPrice).filter(BitcoinPrice.id == 1).first()
            if btc_price:
                btc_price.price = new_price
            else:
                session.add(BitcoinPrice(id=1, price=new_price))

    async def get_bitcoin_price(self):
        return await asyncio.to_thread(self._get_bitcoin_price)

    def _get_bitcoin_price(self):
        with self._session() as session:
            btc_price = session.query(BitcoinPrice).filter(BitcoinPrice.id == 1).first()
            return btc_price.price if btc_price else None

    # ---- Songs ---------------------------------------------------------------

    async def save_song(self, song_data, requested_by_user_id):
        try:
            await asyncio.to_thread(self._save_song, song_data, requested_by_user_id)
        except Exception:
            self.logger.exception("Error saving song")

    def _save_song(self, song_data, requested_by_user_id):
        with self._session() as session:
            session.add(Song(song_data, requested_by_user_id))

    async def get_most_played_songs(self):
        return await asyncio.to_thread(self._get_most_played_songs)

    def _get_most_played_songs(self):
        with self._session() as session:
            rows = (
                session.query(
                    Song.original_url,
                    Song.title,
                    func.count(Song.id).label("total_plays"),
                )
                .group_by(Song.original_url, Song.title)
                .order_by(func.count(Song.id).desc())
                .limit(5)
                .all()
            )
            return [(r.original_url, r.title, r.total_plays) for r in rows]

    # ---- Data subject requests (GDPR) ---------------------------------------

    async def delete_user_data(self, user_id):
        """Erase all personal data stored for a user."""
        return await asyncio.to_thread(self._delete_user_data, user_id)

    def _delete_user_data(self, user_id):
        with self._session() as session:
            deleted = (
                session.query(User).filter(User.id == user_id).delete()
            )
            session.query(Song).filter(
                Song.requested_by_user_id == user_id
            ).delete()
            return deleted

    async def get_user_data(self, user_id):
        """Return a summary of the personal data stored for a user."""
        return await asyncio.to_thread(self._get_user_data, user_id)

    def _get_user_data(self, user_id):
        with self._session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            song_count = (
                session.query(func.count(Song.id))
                .filter(Song.requested_by_user_id == user_id)
                .scalar()
            )
            return {
                "tracked_seconds": user.total_duration_seconds if user else 0,
                "songs_requested": song_count or 0,
            }

    async def get_most_song_requests(self):
        return await asyncio.to_thread(self._get_most_song_requests)

    def _get_most_song_requests(self):
        with self._session() as session:
            rows = (
                session.query(
                    Song.requested_by_user_id,
                    func.count(Song.id).label("total_requests"),
                )
                .group_by(Song.requested_by_user_id)
                .order_by(func.count(Song.id).desc())
                .limit(5)
                .all()
            )
            return [(r.requested_by_user_id, r.total_requests) for r in rows]


async def setup(bot):
    await bot.add_cog(Database(bot))
