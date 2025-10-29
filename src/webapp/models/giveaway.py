import random
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, JSON
from sqlalchemy.orm import relationship

from src.webapp.database import Base
from config import MOSCOW_TZ


def random_id():
    return random.randint(10**6, 10**7 - 1)

class Giveaway(Base):
    __tablename__ = "giveaways"

    id = Column(Integer, primary_key=True, autoincrement=False, default=random_id)
    name = Column(String, nullable=False)
    prize = Column(JSON, nullable=False)

    description = Column(Text, nullable=True)
    start_date = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(MOSCOW_TZ),
        nullable=True
    )
    channel_username = Column(String, nullable=False, default="peptides_ru")
    minimal_order_amount = Column(Numeric(precision=2), nullable=False, default=0.00)
    minimal_review_grade = Column(Integer, nullable=False, default=4)
    minimal_review_length = Column(Integer, nullable=False, default=100)
    minimal_referral_amount = Column(Integer, nullable=False, default=3)

    end_date = Column(DateTime(timezone=True), nullable=True)
    participants = relationship(
        "Participant",
        back_populates="giveaway",
        cascade="all, delete-orphan"
    )