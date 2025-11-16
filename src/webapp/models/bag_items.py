from sqlalchemy import Column, BigInteger, Integer, ForeignKey
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class BagItem(Base):
    __tablename__ = "bag_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True, nullable=False)

    # Link to bag
    bag_id = Column(BigInteger, ForeignKey("bags.id"), nullable=False, index=True)

    # Basic item info (you can adapt to your real product model later)
    product_id = Column(BigInteger, nullable=True)
    quantity = Column(Integer, nullable=False, default=1)

    bag = relationship(
        "Bag",
        back_populates="items",
    )