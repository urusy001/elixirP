from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    onec_id = Column(String, index=True, unique=True, nullable=False)
    product_onec_id = Column(String, ForeignKey("products.onec_id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    code = Column(String, index=True, nullable=False)
    file_id = Column(String, index=True, nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    balance = Column(Integer, nullable=False, default=0)

    # Relationship
    product = relationship("Product", back_populates="features")
    cart_items = relationship("CartItem", back_populates="product", lazy="selectin", cascade="all, delete-orphan")
