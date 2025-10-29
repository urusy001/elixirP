from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, DateTime, ForeignKey, Boolean, String
)
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Participant(Base):
    __tablename__ = "participants"

    giveaway_id = Column(
        Integer,
        ForeignKey("giveaways.id", ondelete="CASCADE"),
        primary_key=True
    )
    tg_id = Column(BigInteger, primary_key=True, index=True)
    ref_id = Column(BigInteger, index=True, nullable=True, default=None)

    completed_subscription = Column(Boolean, nullable=False, default=False)
    completed_refs = Column(Boolean, nullable=False, default=False)
    completed_deal = Column(Boolean, nullable=False, default=False)
    completed_review = Column(Boolean, nullable=False, default=False)

    deal_code = Column(BigInteger, nullable=True, default=None)
    review_id = Column(Integer, nullable=True, default=None)
    review_email = Column(String, nullable=True, default=None)
    review_phone = Column(String, nullable=True, default=None)
    review_fullname = Column(String, nullable=True, default=None)
    participation_code = Column(String, nullable=True, default=None)

    giveaway = relationship("Giveaway", back_populates="participants")

    @property
    def is_completed(self) -> bool:
        return all([
            self.completed_subscription,
            self.completed_refs,
            self.completed_deal,
            self.completed_review
        ])
