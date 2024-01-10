import asyncio
from sqlalchemy import (
    JSON,
    Boolean,
    String,
    Text,
    create_engine,
    Column,
    Integer,
    text,
    BigInteger,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    total_duration_seconds = Column(Integer, default=0)


class ChessGame(Base):
    __tablename__ = "chess_games"
    id = Column(String(255), primary_key=True)  # Adjust the length as needed
    rated = Column(Boolean)
    variant = Column(String(50))
    speed = Column(String(50))
    perf = Column(String(50))
    createdAt = Column(BigInteger)
    lastMoveAt = Column(BigInteger)
    status = Column(String(50))
    players = Column(JSON)
    opening = Column(JSON)
    moves = Column(Text, nullable=True)
    clock = Column(JSON, nullable=True)
    winner = Column(Text, nullable=True)

    def __init__(self, game_data):
        self.id = game_data["id"]
        self.rated = game_data["rated"]
        self.variant = game_data["variant"]
        self.speed = game_data["speed"]
        self.perf = game_data["perf"]
        self.createdAt = game_data["createdAt"]
        self.lastMoveAt = game_data["lastMoveAt"]
        self.status = game_data["status"]
        self.players = game_data["players"]
        self.opening = game_data["opening"]
        self.moves = game_data.get("moves", None)
        self.clock = game_data.get("clock", None)
        self.winner = game_data.get("winner", None)


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
