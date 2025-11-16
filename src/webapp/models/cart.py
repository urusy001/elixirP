from sqlalchemy import BigInteger, Numeric, Column, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True, nullable=False)

    # Owner
    tg_id = Column(BigInteger, ForeignKey("users.tg_id"), nullable=False, index=True)

    # Associated bag
    bag_id = Column(BigInteger, ForeignKey("bags.id"), nullable=False, index=True)

    total = Column(Numeric(10, 2), nullable=False, default=0.00)
    last_updated = Column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    user = relationship(
        "User",
        back_populates="carts",
    )

    bag = relationship(
        "Bag",
        back_populates="carts",
        foreign_keys=[bag_id],
    )