from sqlalchemy import Column, BigInteger, String, DateTime

from src.webapp.database import Base


class User(Base):
    __tablename__ = "users"

    # Telegram + identity
    tg_id = Column(BigInteger, primary_key=True, index=True, autoincrement=False)
    tg_ref_id = Column(BigInteger, index=True, autoincrement=False, nullable=True)
    tg_phone = Column(String, nullable=False, index=True)

    # Profile info
    name = Column(String, nullable=True, default=None)
    surname = Column(String, nullable=True, default=None)
    email = Column(String, unique=True, nullable=True, default=None)
    phone = Column(String, unique=True, nullable=True, default=None)

    # Thread & tokens
    thread_id = Column(String, nullable=True, default=None)
    input_tokens = Column(BigInteger, nullable=False, default=0)
    output_tokens = Column(BigInteger, nullable=False, default=0)

    # Blocking system
    blocked_until = Column(DateTime(timezone=True), nullable=True, default=None)
