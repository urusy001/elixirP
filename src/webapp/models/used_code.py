import random
from sqlalchemy import BigInteger, Column, ForeignKey, String, Numeric, Index, UniqueConstraint
from src.webapp.database import Base


class UsedCode(Base):
    __tablename__ = "used_codes"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=False,
        index=True,
        nullable=False,
        default=lambda: random.randint(10**6, 10**7 - 1),
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.tg_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code = Column(String, nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        # if a code should be used only once globally:
        UniqueConstraint("code", name="uq_used_codes_code"),
        Index("ix_used_codes_user_id_code", "user_id", "code"),
    )