from sqlalchemy import Column, BigInteger, Integer
from services.db_service.base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    total_duration_seconds = Column(Integer, default=0)
