from sqlalchemy import Column, Integer, Float
from cogs.db.base import Base


class BitcoinPrice(Base):
    __tablename__ = "bitcoin_price"
    id = Column(Integer, primary_key=True, default=1)
    price = Column(Float, nullable=False)
