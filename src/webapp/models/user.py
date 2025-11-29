from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.orm import relationship

from src.webapp.database import Base


class User(Base):
    __tablename__ = "users"

    tg_id = Column(BigInteger, primary_key=True, index=True, autoincrement=False)
    tg_ref_id = Column(BigInteger, index=True, autoincrement=False, nullable=True, default=None)
    tg_phone = Column(String, nullable=True, index=True, default=None)

    photo_url = Column(String, nullable=True, default=None)
    name = Column(String, nullable=True, default=None)
    surname = Column(String, nullable=True, default=None)
    email = Column(String, unique=True, nullable=True, default=None)
    phone = Column(String, unique=True, nullable=True, default=None)

    thread_id = Column(String, nullable=True, default=None)
    input_tokens = Column(BigInteger, nullable=False, default=0)
    output_tokens = Column(BigInteger, nullable=False, default=0)

    # Blocking system
    blocked_until = Column(DateTime(timezone=True), nullable=True, default=None)

    carts = relationship(
        "Cart",
        back_populates="user",
        cascade="all, delete-orphan",
    )