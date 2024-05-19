from sqlalchemy import (
    JSON,
    Boolean,
    String,
    Text,
    Column,
    BigInteger,
)
from cogs.db.base import Base


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
