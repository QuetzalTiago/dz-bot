import asyncio
from sqlalchemy import (
    create_engine,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from services.db_service.entities.btc_price import BitcoinPrice

from services.db_service.entities.chess_game import ChessGame
from services.db_service.entities.startup_notification import StartupNotification
from services.db_service.entities.user import User
from services.db_service.base import Base


class DatabaseService:
    def __init__(self, db_url):
        self.db_url = db_url
        self.db_name = "discord_bot"  # Set the database name here

    async def async_initialize(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.initialize)

    def initialize(self):
        # Connect without a specific database to execute initial setup commands
        engine = create_engine(self.db_url)
        conn = engine.connect()

        # Check if database exists, if not create it
        db_exist = conn.execute(
            text(f"SHOW DATABASES LIKE '{self.db_name}';")
        ).fetchone()
        if not db_exist:
            try:
                # Use raw connection for DDL statement
                conn.execute(text(f"CREATE DATABASE {self.db_name};"))
                print(f"Database {self.db_name} created.")
            except Exception as e:
                print(f"Failed to create database: {e}")
                # Handle exceptions or errors as needed
                raise

        conn.close()

        # Now, reconnect with the specific database
        self.engine = create_engine(f"{self.db_url}/{self.db_name}")
        Base.metadata.bind = self.engine

        # Prepare session and create tables
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

        print("DB connection initialized")

    def update_user_duration(self, user_id, additional_seconds):
        session = self.Session()
        user = session.query(User).filter(User.id == user_id).first()

        if user is None:
            # If the user doesn't exist, create a new one with the initial duration
            user = User(id=user_id, total_duration_seconds=additional_seconds)
            session.add(user)
        else:
            # If the user exists, update the total duration
            user.total_duration_seconds += additional_seconds

        session.commit()
        print("User tracking updated")
        session.close()

    def get_user_hours(self, user_id):
        session = self.Session()
        user = session.query(User).filter(User.id == user_id).first()

        if user is not None:
            total_hours = user.total_duration_seconds / 3600
            session.close()
            return total_hours
        else:
            # In case user doesn't exist, return 0 or handle appropriately
            session.close()
            return 0

    def get_all_user_hours(self):
        session = self.Session()
        try:
            # Fetch all users and their durations
            users = session.query(User.id, User.total_duration_seconds).all()
            # Convert seconds to hours and return
            user_hours = [
                (user_id, total_seconds / 3600) for user_id, total_seconds in users
            ]
            return user_hours
        finally:
            session.close()

    def save_chess_game(self, game_data):
        session = self.Session()
        try:
            chess_game = ChessGame(game_data)
            session.add(chess_game)
            session.commit()
        except Exception as e:
            print(e)
            print(f"Error saving chess game: {e}")
            session.rollback()
        finally:
            session.close()

    def set_startup_notification(self, message_id, channel_id):
        session = self.Session()
        try:
            notification = session.query(StartupNotification).first()
            if not notification:
                notification = StartupNotification(
                    notify_on_startup=True, message_id=message_id, channel_id=channel_id
                )
                session.add(notification)
            else:
                notification.notify_on_startup = True
                notification.message_id = message_id
                notification.channel_id = channel_id
            session.commit()
        except Exception as e:
            print(f"Error setting startup notification: {e}")
            session.rollback()
        finally:
            session.close()

    def get_startup_notification(self):
        session = self.Session()
        try:
            notification = session.query(StartupNotification).first()
            if notification and notification.notify_on_startup:
                return notification.message_id, notification.channel_id
            return None, None
        finally:
            session.close()

    def get_chess_games(self):
        session = self.Session()
        try:
            chess_games = session.query(ChessGame).all()

            return chess_games

        except Exception as e:
            print(f"Error fetching chess games: {e}")
        finally:
            session.close()

    def update_bitcoin_price(self, new_price):
        session = self.Session()
        try:
            btc_price = session.query(BitcoinPrice).filter(BitcoinPrice.id == 1).first()
            if btc_price:
                btc_price.price = new_price
            else:
                btc_price = BitcoinPrice(id=1, price=new_price)
                session.add(btc_price)
            session.commit()
        except Exception as e:
            print(f"Error updating Bitcoin price: {e}")
            session.rollback()
        finally:
            session.close()

    def get_bitcoin_price(self):
        session = self.Session()
        try:
            btc_price = session.query(BitcoinPrice).filter(BitcoinPrice.id == 1).first()
            return btc_price.price if btc_price else None
        finally:
            session.close()
