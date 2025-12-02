import random
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, JSON, Boolean
from sqlalchemy.orm import relationship

from config import MOSCOW_TZ
from src.webapp.database import Base


def random_id():
    return random.randint(10 ** 6, 10 ** 7 - 1)


class Giveaway(Base):
    __tablename__ = "giveaways"

    id = Column(Integer, primary_key=True, autoincrement=False, default=random_id)
    name = Column(String, nullable=False)
    prize = Column(JSON, nullable=False)

    description = Column(Text, nullable=True)
    start_date = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(MOSCOW_TZ),
        nullable=True,
    )
    channel_username = Column(String, nullable=False, default="peptides_ru")
    minimal_order_amount = Column(Numeric(10, 2), nullable=False, default=0.00)
    minimal_review_grade = Column(Integer, nullable=False, default=4)
    minimal_review_length = Column(Integer, nullable=False, default=100)
    minimal_referral_amount = Column(Integer, nullable=False, default=3)

    end_date = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(MOSCOW_TZ) + timedelta(days=30),
    )

    closed = Column(Boolean, nullable=False, default=False)
    closed_message = Column(Text, nullable=True)

    participants = relationship(
        "Participant",
        back_populates="giveaway",
        cascade="all, delete-orphan",
    )

#TODO: Add unique column to define whether the giveaway codes need to be given 1 for all or 1 for 1
#TODO: Add availability to change giveaway attributes from bot's admin panel