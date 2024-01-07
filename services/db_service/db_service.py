import asyncio
from sqlalchemy import (
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
            # Calculate the total duration in hours
            total_hours = (
                user.total_duration_seconds / 3600
            )  # converting seconds to hours
            session.close()
            return total_hours
        else:
            # In case user doesn't exist, return 0 or handle appropriately
            session.close()
            return 0
