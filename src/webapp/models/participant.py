from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, DateTime, ForeignKey, UniqueConstraint, Boolean
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
    completed_refs = Column(Boolean, default=False)
    completed_deal = Column(Boolean, default=False)
    deal_code = Column(BigInteger, nullable=True, default=None)
    completed_review = Column(Boolean, nullable=False, default=False)

    giveaway = relationship("Giveaway", back_populates="participants")
