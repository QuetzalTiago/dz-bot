from sqlalchemy import Column, Integer, Float
from services.db_service.base import Base


class BitcoinPrice(Base):
    __tablename__ = "bitcoin_price"
    id = Column(Integer, primary_key=True, default=1)
    price = Column(Float, nullable=False)
