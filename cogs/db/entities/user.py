from sqlalchemy import Column, BigInteger, Integer
from cogs.db.base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    total_duration_seconds = Column(Integer, default=0)
