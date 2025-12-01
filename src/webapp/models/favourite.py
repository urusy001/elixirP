from sqlalchemy import Column, BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class Favourite(Base):
    __tablename__ = "favourites"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.tg_id", ondelete="CASCADE"), index=True, nullable=False)
    onec_id = Column(String, ForeignKey("products.onec_id", ondelete="CASCADE"), index=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "onec_id", name="uq_favourites_user_product"),
    )

    user = relationship("User", back_populates="favourites")
    product = relationship("Product", back_populates="favourited_by")