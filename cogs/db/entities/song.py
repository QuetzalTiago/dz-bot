from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    String,
)
from cogs.db.base import Base


class Song(Base):
    __tablename__ = "songs"
    id = Column(Integer, primary_key=True)  # Auto-generated primary key
    title = Column(String(255))
    original_url = Column(String(255))
    artist = Column(String(100))
    requested_by_user_id = Column(BigInteger)

    def __init__(self, song_data, requested_by_user_id):
        self.title = song_data["title"]
        self.original_url = song_data["original_url"]
        self.artist = song_data.get("uploader", "N/A")
        self.requested_by_user_id = requested_by_user_id
