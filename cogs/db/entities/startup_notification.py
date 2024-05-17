from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    Text,
)
from cogs.db.base import Base


class StartupNotification(Base):
    __tablename__ = "startup_notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    notify_on_startup = Column(Boolean, default=False)
    message_id = Column(Text)
    channel_id = Column(Text)
